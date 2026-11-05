"""
The standard workbook: the template the app generates, reading and syncing
it, the checks a sync runs, and the pages around it.
"""
from datetime import date, timedelta

import pytest
from openpyxl import load_workbook

from app.extensions import db
from app.models.ledger import Payout, PayoutPurpose, Rate, SyncRun, YearSummary
from app.models.member import (
    PAID, PARTIAL, UNPAID, Contribution, Member, MemberAlias, MemberYear, PeriodSummary,
)
from app.models.report import GeneratedReport
from app.services.period_store import PeriodStore
from app.services.standard_sync import StandardSync
from app.services.standard_workbook import StandardWorkbook
from app.services.workbook_template import build_template
from tests.workbooks import build_standard_workbook

MEMBERS = [
    ('M001', 'Ann Banda', date(2024, 1, 1), None),
    ('M002', 'Ben Phiri', date(2024, 1, 1), None),
    ('M003', 'Cara Mwale', date(2025, 3, 1), None),    # joins March 2025
]


# Payout purposes are each group's own; these tests' group pays out for these
PURPOSES = ['Funeral condolence', 'Wedding gift', 'Sick patient grant']


@pytest.fixture(autouse=True)
def purposes(app, group):
    db.session.add_all(PayoutPurpose(group_id=group.id, name=name) for name in PURPOSES)
    db.session.commit()


def _book(tmp_path, members=MEMBERS, contributions=None, **kw):
    contributions = contributions if contributions is not None else {
        2025: [
            ('M001', 'Ann Banda', {'January': 1000, 'February': 1000, 'March': 1000}),
            ('M002', 'Ben Phiri', {'January': 1000, 'March': 500}),
            ('M003', 'Cara Mwale', {'March': 1000}),
        ],
    }
    return build_standard_workbook(tmp_path / 'book.xlsx', members, contributions, **kw)


def _sync(group, path):
    return StandardSync.sync(group, str(path))


def _month(group, year, month):
    return {
        c.member.display_name: (c.amount, c.status)
        for c in Contribution.for_group(group.id).filter_by(year=year, month=month)
    }


def _messages(run):
    return [f"{w['where']}: {w['message']}" for w in run.warnings]


# ==================== TEMPLATE ====================

def test_template_is_prefilled_and_reads_back(app, group, tmp_path):
    db.session.add_all([
        Member(group_id=group.id, display_name='Ann Banda', normalised_name='ann banda'),
        Member(group_id=group.id, display_name='Ben Phiri', normalised_name='ben phiri', code='M007'),
    ])
    db.session.commit()

    path = tmp_path / 'template.xlsx'
    path.write_bytes(build_template(group, 2026).getvalue())
    wb = load_workbook(path)

    assert wb.sheetnames == ['Read me', 'Members', 'Contributions 2026', 'Payouts', 'Rates', 'Summary', 'Lists']
    assert wb['Lists'].sheet_state == 'hidden'
    codes = {m.display_name: m.code for m in Member.for_group(group.id)}
    assert codes == {'Ann Banda': 'M001', 'Ben Phiri': 'M007'}   # existing IDs kept
    assert [wb['Members'].cell(r, 1).value for r in (2, 3)] == ['M001', 'M007']
    assert [wb['Contributions 2026'].cell(r, 1).value for r in (2, 3)] == ['M001', 'M007']
    assert wb['Contributions 2026']['B2'].value.startswith('=IF(A2=""')
    assert wb['Summary']['E2'].value == '=B2+C2-D2'
    assert [c.value for c in wb['Lists']['A'][1:]] == ['Funeral condolence', 'Sick patient grant', 'Wedding gift']
    assert {dv.formula1 for dv in wb['Payouts'].data_validations.dataValidation} == {
        '=Members!$A$2:$A$2000', '=Lists!$A$2:$A$200'}

    # The untouched template is recognised and syncs cleanly
    assert StandardWorkbook.is_standard(str(path))
    run = _sync(group, path)
    assert run.details['months'] == []
    assert Member.for_group(group.id).count() == 2


def test_filled_in_template_syncs(app, group, tmp_path):
    db.session.add(Member(group_id=group.id, display_name='Ann Banda', normalised_name='ann banda'))
    db.session.commit()
    path = tmp_path / 'template.xlsx'
    path.write_bytes(build_template(group, 2026).getvalue())
    wb = load_workbook(path)
    wb['Contributions 2026']['C2'] = 1000     # Ann, January
    wb['Rates']['B2'] = 1000
    wb.save(path)

    _sync(group, path)

    assert _month(group, 2026, 1) == {'Ann Banda': (1000, PAID)}
    assert Rate.for_group(group.id).one().amount == 1000


def test_template_carries_over_the_previous_closing_balance(app, group):
    db.session.add(YearSummary(group_id=group.id, year=2025, opening_balance=0,
                               total_contributions=5000, total_payouts=1000, closing_balance=4000))
    db.session.commit()
    wb = load_workbook(build_template(group, 2026))
    assert wb['Summary']['B2'].value == 4000


def test_template_download_page(client, group, make_user, login):
    make_user()
    login()
    response = client.post('/workbook/template', data={'year': '2026'})
    assert response.mimetype.endswith('spreadsheetml.sheet')
    assert 'mzugoss_contributions_2026.xlsx' in response.headers['Content-Disposition']


# ==================== READING ====================

def test_missing_header_is_an_error(app, group, tmp_path):
    path = _book(tmp_path)
    wb = load_workbook(path)
    wb['Contributions 2025']['A1'] = 'Who'
    wb.save(path)

    with pytest.raises(ValueError, match="Contributions 2025' is missing the column.*Member ID"):
        _sync(group, path)


def test_columns_are_found_by_header_in_any_order(app, group, tmp_path):
    path = _book(tmp_path)
    wb = load_workbook(path)
    ws = wb['Members']
    for row in ws.iter_rows():
        row[0].value, row[1].value = row[1].value, row[0].value   # swap Name and Member ID
    wb.save(path)

    _sync(group, path)

    assert {m.code for m in Member.for_group(group.id)} == {'M001', 'M002', 'M003'}


def test_text_in_an_amount_cell_is_a_warning(app, group, tmp_path):
    path = _book(tmp_path, contributions={2025: [('M001', 'Ann Banda', {'January': 'pending'}),
                                                 ('M002', 'Ben Phiri', {'January': 1000})]})
    run = _sync(group, path)
    assert "Contributions 2025 row 2, January: 'pending' is not an amount, so it was ignored." in _messages(run)
    assert _month(group, 2025, 1)['Ann Banda'] == (0, UNPAID)


# ==================== CONTRIBUTIONS ====================

def test_every_month_with_payments_is_stored_and_blank_months_skipped(app, group, tmp_path):
    run = _sync(group, _book(tmp_path))

    assert run.details['months'] == [[2025, 1], [2025, 2], [2025, 3]]
    assert PeriodSummary.for_group(group.id).count() == 3
    assert Contribution.for_group(group.id).filter_by(month=4).count() == 0


def test_months_before_joining_are_not_counted_against_a_member(app, group, tmp_path):
    _sync(group, _book(tmp_path))

    assert 'Cara Mwale' not in _month(group, 2025, 1)            # not a member yet
    assert _month(group, 2025, 2)['Ben Phiri'] == (0, UNPAID)    # a member who didn't pay
    assert _month(group, 2025, 3)['Cara Mwale'] == (1000, PAID)
    summary = PeriodSummary.for_group(group.id).filter_by(year=2025, month=1).one()
    assert (summary.contributors_count, summary.defaulters_count) == (2, 0)


def test_payment_outside_membership_is_a_warning(app, group, tmp_path):
    run = _sync(group, _book(tmp_path, contributions={2025: [('M003', 'Cara Mwale', {'January': 1000})]}))

    assert any('Cara Mwale paid 1,000 outside their Joined / Left months' in m for m in _messages(run))
    assert _month(group, 2025, 1)['Cara Mwale'] == (1000, PAID)   # still recorded


def test_left_members_stop_being_counted(app, group, tmp_path):
    members = [('M001', 'Ann Banda', None, None), ('M002', 'Ben Phiri', None, date(2025, 1, 1))]
    _sync(group, _book(tmp_path, members=members, contributions={2025: [
        ('M001', 'Ann Banda', {'January': 1000, 'February': 1000}), ('M002', 'Ben Phiri', {}),
    ]}))

    assert _month(group, 2025, 1) == {'Ann Banda': (1000, PAID), 'Ben Phiri': (0, UNPAID)}
    assert _month(group, 2025, 2) == {'Ann Banda': (1000, PAID)}
    assert not Member.for_group(group.id).filter_by(code='M002').one().is_active


def test_rates_mark_partial_payments(app, group, tmp_path):
    _sync(group, _book(tmp_path, rates=[(date(2024, 1, 1), 500), (date(2025, 3, 1), 1000)]))

    assert _month(group, 2025, 1)['Ben Phiri'] == (1000, PAID)    # rate 500
    assert _month(group, 2025, 3)['Ben Phiri'] == (500, PARTIAL)  # rate now 1000


def test_paying_above_the_rate_covers_the_next_months(app, group, tmp_path):
    members = [('M001', 'Ann Banda', None, None), ('M002', 'Ben Phiri', None, None)]
    _sync(group, _book(tmp_path, members=members, rates=[(date(2025, 1, 1), 1000)], contributions={2025: [
        ('M001', 'Ann Banda', {'January': 2500}),                       # pays ahead
        ('M002', 'Ben Phiri', {'January': 1000, 'February': 1000, 'March': 1000}),
    ]}))

    ann = {m: Contribution.for_group(group.id).filter_by(year=2025, month=m).join(Member)
           .filter(Member.code == 'M001').one() for m in (1, 2, 3)}
    assert [(c.amount, c.credit_used, c.status) for c in ann.values()] == [
        (2500, 0, PAID), (0, 1000, PAID), (0, 500, PARTIAL)]
    # Money is counted when received, not when credit is used
    totals = {s.month: s.total_contributions for s in PeriodSummary.for_group(group.id)}
    assert totals == {1: 3500, 2: 1000, 3: 1000}
    assert MemberYear.for_group(group.id).count() == 0   # credit used up within the year


def test_excess_is_credit_for_next_years_first_months(app, group, tmp_path):
    members = [('M001', 'Ann Banda', None, None), ('M002', 'Ben Phiri', None, None)]
    path = _book(tmp_path, members=members, rates=[(date(2025, 1, 1), 1000)],
                 summary=[(2025, 0, None, None, None)], contributions={
                     2025: [('M001', 'Ann Banda', {m: 1000 for m in ('January', 'February')}),
                            ('M002', 'Ben Phiri', {m: 1000 for m in ('January', 'February')})],
                     2026: [('M001', 'Ann Banda', {'March': 1000}),
                            ('M002', 'Ben Phiri', {'January': 1000, 'February': 1000, 'March': 1000})],
                 })
    wb = load_workbook(path)
    wb['Contributions 2025']['O1'] = 'Excess'
    wb['Contributions 2025']['O2'] = 1500     # Ann paid 1,500 extra in 2025
    wb.save(path)

    _sync(group, path)

    assert _month(group, 2026, 1)['Ann Banda'] == (0, PAID)       # covered by credit
    assert _month(group, 2026, 2)['Ann Banda'] == (0, PARTIAL)    # 500 left
    assert _month(group, 2026, 3)['Ann Banda'] == (1000, PAID)
    year = MemberYear.for_group(group.id).filter_by(year=2025).one()
    assert (year.credit_in, year.excess_paid, year.credit_out) == (0, 1500, 1500)

    balances = {y.year: y for y in YearSummary.for_group(group.id)}
    assert balances[2025].total_contributions == 5500              # 4,000 + 1,500 excess
    jan = PeriodSummary.for_group(group.id).filter_by(year=2026, month=1).one()
    assert (jan.contributors_count, jan.defaulters_count) == (2, 0)
    paid = {p['name']: (p['amount'], p['credit']) for p in PeriodStore.paid_members(group.id, 2026, 1)}
    assert paid['Ann Banda'] == (1000, 1000)


def test_template_has_an_excess_column(app, group):
    wb = load_workbook(build_template(group, 2026))
    assert wb['Contributions 2026']['O1'].value == 'Excess'
    assert "!C2:O" in wb['Summary']['C2'].value


def test_member_missing_from_a_years_sheet_is_unpaid_with_a_warning(app, group, tmp_path):
    run = _sync(group, _book(tmp_path, contributions={2025: [('M001', 'Ann Banda', {'January': 1000})]}))

    # Paid nothing that year, but still a member
    assert _month(group, 2025, 1) == {'Ann Banda': (1000, PAID), 'Ben Phiri': (0, UNPAID)}
    assert any('M002 Ben Phiri is a member in 2025 but has no row, so they are counted as unpaid' in m
               for m in _messages(run))


def test_unknown_and_duplicate_member_ids_are_warnings(app, group, tmp_path):
    members = MEMBERS + [('M001', 'Someone Else', None, None)]
    run = _sync(group, _book(tmp_path, members=members, contributions={2025: [
        ('M001', 'Ann Banda', {'January': 1000}), ('M099', None, {'January': 1000}),
    ]}))

    messages = _messages(run)
    assert any('Member ID M001 is also used on row 2' in m for m in messages)
    assert any('Member ID M099 is not on the Members sheet' in m for m in messages)
    assert Member.for_group(group.id).filter_by(display_name='Someone Else').count() == 0


def test_resync_matches_by_member_id_and_keeps_old_spellings(app, group, tmp_path):
    _sync(group, _book(tmp_path))
    renamed = [('M001', 'Ann Banda-Zulu', date(2024, 1, 1), None)] + MEMBERS[1:]

    _sync(group, _book(tmp_path, members=renamed))

    ann = Member.for_group(group.id).filter_by(code='M001').one()
    assert ann.display_name == 'Ann Banda-Zulu'
    assert [a.normalised_name for a in ann.aliases] == ['ann banda']
    assert Member.for_group(group.id).count() == 3


def test_legacy_members_are_matched_and_given_their_id(app, group, tmp_path):
    db.session.add(Member(group_id=group.id, display_name='Ann  Banda', normalised_name='ann banda'))
    db.session.commit()

    run = _sync(group, _book(tmp_path))

    assert run.details['new_members'] == ['Ben Phiri', 'Cara Mwale']
    assert Member.for_group(group.id).filter_by(normalised_name='ann banda').one().code == 'M001'


# ==================== PAYOUTS AND BALANCES ====================

def test_payouts_are_stored_and_checked(app, group, tmp_path):
    future = date.today() + timedelta(days=30)
    run = _sync(group, _book(tmp_path, payouts=[
        (date(2025, 2, 10), 'M001', 'Ann Banda', 'Funeral condolence', 5000, 'Chair'),
        (date(2025, 2, 10), 'M001', 'Ann Banda', 'funeral condolence', 5000, 'Chair'),  # repeat
        (date(2025, 3, 1), 'M002', 'Ben Phiri', 'Party', 2000, 'Chair'),                # unknown purpose
        (date(2025, 3, 2), 'M050', None, 'Wedding gift', 1000, 'Chair'),                # unknown member
        (future, 'M002', 'Ben Phiri', 'Wedding gift', 1000, 'Chair'),
        ('not a date', 'M002', 'Ben Phiri', 'Wedding gift', 1000, 'Chair'),
    ]))

    messages = _messages(run)
    assert 'Payouts row 3: Looks like a repeat of row 2 (same member, amount and date).' in messages
    assert "Payouts row 4: Purpose 'Party' is not one of the group's payout purposes." in messages
    assert 'Payouts row 5: Member ID M050 is not on the Members sheet.' in messages
    assert any(m.startswith('Payouts row 6: The date') and 'future' in m for m in messages)
    assert 'Payouts row 7: Has no valid date, so it is not counted in any year.' in messages

    assert Payout.for_group(group.id).count() == 5
    first = Payout.for_group(group.id).order_by(Payout.sheet_row).first()
    assert (first.beneficiary, first.purpose, first.year) == ('Ann Banda', 'Funeral condolence', 2025)


def test_balances_carry_over_and_monthly_figures_are_calculated(app, group, tmp_path):
    contributions = {
        2024: [('M001', 'Ann Banda', {'December': 1000}), ('M002', 'Ben Phiri', {'December': 1000})],
        2025: [('M001', 'Ann Banda', {'January': 1000, 'February': 1000}),
               ('M002', 'Ben Phiri', {'January': 1000})],
    }
    _sync(group, _book(tmp_path, contributions=contributions,
                       payouts=[(date(2025, 2, 10), 'M001', 'Ann Banda', 'Wedding gift', 1500, 'Chair')],
                       summary=[(2024, 10000, None, None, None), (2025, None, None, None, None)]))

    years = {y.year: y for y in YearSummary.for_group(group.id)}
    assert (years[2024].opening_balance, years[2024].closing_balance) == (10000, 12000)
    assert (years[2025].opening_balance, years[2025].total_contributions,
            years[2025].total_payouts, years[2025].closing_balance) == (12000, 3000, 1500, 13500)

    feb = PeriodSummary.for_group(group.id).filter_by(year=2025, month=2).one()
    assert (feb.money_dispensed, feb.book_balance) == (1500, 13500)
    jan = PeriodSummary.for_group(group.id).filter_by(year=2025, month=1).one()
    assert (jan.money_dispensed, jan.book_balance) == (0, 14000)


def test_summary_sheet_disagreements_are_warnings(app, group, tmp_path):
    contributions = {
        2024: [('M001', 'Ann Banda', {'December': 1000})],
        2025: [('M001', 'Ann Banda', {'January': 1000})],
    }
    run = _sync(group, _book(tmp_path, contributions=contributions, summary=[
        (2024, 5000, 1000, 0, 6000),        # right
        (2025, 8000, 1000, 0, 9000),        # typed carry-over: 2024 closed at 6,000
    ]))

    messages = _messages(run)
    assert 'Summary 2025: Opening balance is 8,000, but 2024 closed at 6,000.' in messages
    assert 'Summary 2025: The sheet shows closing balance of 9,000, but the app calculates 7,000.' in messages
    assert not any(m.startswith('Summary 2024') for m in messages)


def test_missing_opening_balance_is_a_warning(app, group, tmp_path):
    run = _sync(group, _book(tmp_path))
    assert 'Summary: No opening balance for 2025; 0 was used.' in _messages(run)


# ==================== UPLOAD ====================

def _upload(client, path, month='3', year='2025'):
    with open(path, 'rb') as fh:
        return client.post('/upload', data={'file': (fh, 'book.xlsx'), 'year': year, 'month': month},
                           content_type='multipart/form-data')


def test_uploading_a_standard_workbook_reports_the_chosen_month(client, group, make_user, login, tmp_path):
    make_user()
    login()

    response = _upload(client, _book(tmp_path, summary=[(2025, 0, None, None, None)]))

    assert response.headers['Location'] == '/reports/preview'
    report = GeneratedReport.query.one()
    assert (report.year, report.month, report.total_contributions, report.contributors_count) == (2025, 3, 2500, 3)
    run = SyncRun.query.one()
    assert (run.layout, run.synced_by) == ('standard', report.generated_by)
    assert client.get(f'/syncs/{run.id}').status_code == 200


def test_uploading_for_a_month_without_payments_points_to_the_sync(client, group, make_user, login, tmp_path):
    make_user()
    login()

    response = _upload(client, _book(tmp_path), month='9')

    run = SyncRun.query.one()
    assert response.headers['Location'] == f'/syncs/{run.id}'
    assert GeneratedReport.query.count() == 0
    assert b'no contributions for September 2025' in client.get(response.headers['Location']).data


def test_legacy_upload_is_recorded_as_a_sync(client, group, make_user, login, mzugoss_workbook):
    make_user()
    login()
    with open(mzugoss_workbook, 'rb') as fh:
        client.post('/upload', data={'file': (fh, 'm.xlsx'), 'year': '2026', 'month': '3'},
                    content_type='multipart/form-data')

    run = SyncRun.query.one()
    assert (run.layout, run.details['months']) == ('legacy', [[2026, 3]])
    assert len(run.details['new_members']) == 7


def test_workbook_page(client, group, make_user, login, tmp_path):
    make_user()
    login()
    _upload(client, _book(tmp_path, summary=[(2025, 100, None, None, None)]))

    page = client.get('/workbook').data
    assert b'5,600' in page          # closing: 100 opening + 5,500 paid in Jan–Mar
    assert b'Details' in page


def test_sync_pages_are_scoped_and_need_upload_data(client, group, make_group, make_user, login, tmp_path):
    other = make_group(name='Another Welfare', slug='another')
    theirs = _sync(other, _book(tmp_path))
    make_user(email='sec@example.com', role='Secretary')
    make_user(email='chair@example.com')

    login('sec@example.com')
    assert client.get('/workbook').status_code != 200
    client.get('/auth/logout')
    login('chair@example.com')
    assert client.get(f'/syncs/{theirs.id}').status_code == 404


# ==================== PAYOUT PURPOSES ====================

def test_purposes_can_be_added_renamed_and_retired(client, group, make_user, login):
    make_user()
    login()

    client.post('/settings/payout-purposes', data={'name': '  School   fees '})
    client.post('/settings/payout-purposes', data={'name': 'school fees'})      # duplicate
    names = {p.name for p in PayoutPurpose.for_group(group.id)}
    assert names == {'Funeral condolence', 'Wedding gift', 'Sick patient grant', 'School fees'}

    fees = PayoutPurpose.for_group(group.id).filter_by(name='School fees').one()
    client.post(f'/settings/payout-purposes/{fees.id}/rename', data={'name': 'Education grant'})
    client.post(f'/settings/payout-purposes/{fees.id}/toggle')
    fees = db.session.get(PayoutPurpose, fees.id)
    assert (fees.name, fees.is_active) == ('Education grant', False)


def test_retired_purposes_leave_the_template_but_still_match(app, group, tmp_path):
    gift = PayoutPurpose.for_group(group.id).filter_by(name='Wedding gift').one()
    gift.is_active = False
    db.session.commit()

    wb = load_workbook(build_template(group, 2026))
    assert 'Wedding gift' not in [c.value for c in wb['Lists']['A']]
    run = _sync(group, _book(tmp_path, payouts=[(date(2025, 1, 5), 'M001', 'Ann Banda', 'Wedding gift', 100, 'C')]))
    assert not any('purpose' in m.lower() for m in _messages(run))


def test_new_groups_start_with_no_purposes(app, make_group):
    assert PayoutPurpose.for_group(make_group(name='Another Welfare', slug='another').id).count() == 0


def test_purposes_are_per_group_and_need_edit_settings(client, group, make_group, make_user, login):
    other = make_group(name='Another Welfare', slug='another')
    theirs = PayoutPurpose(group_id=other.id, name='School fees')
    db.session.add(theirs)
    db.session.commit()
    make_user(email='t@example.com', role='Treasurer')
    make_user(email='chair@example.com')

    login('t@example.com')
    assert client.get('/settings/payout-purposes').status_code != 200
    client.get('/auth/logout')
    login('chair@example.com')
    assert client.post(f'/settings/payout-purposes/{theirs.id}/toggle').status_code == 404
    assert db.session.get(PayoutPurpose, theirs.id).is_active


# ==================== THE YEAR SO FAR ON REPORTS ====================

_PAYOUTS = [(date(2025, 2, 10), 'M001', 'Ann Banda', 'Wedding gift', 1500, 'Chair'),
            (date(2025, 3, 20), 'M002', 'Ben Phiri', 'Sick patient grant', 2000, 'Chair')]


def test_reports_show_the_year_so_far_and_reconcile(app, group, tmp_path):
    _sync(group, _book(tmp_path, payouts=_PAYOUTS, summary=[(2025, 10000, None, None, None)]))

    figures = {}
    for month in (1, 2, 3):
        data = PeriodStore.report_data(group.id, 2025, month)
        figures[month] = (data['money_dispensed'], data['dispensed_to_date'], data['contributions_to_date'],
                          data['total_book_balance'], len(data['payouts_to_date']))
        assert data['opening_balance'] == 10000
        assert data['opening_balance'] + data['contributions_to_date'] - data['dispensed_to_date'] \
            == data['total_book_balance']

    # Nothing was paid out in January; March's year so far still includes February's payout
    assert figures == {1: (0, 0, 2000, 12000, 0), 2: (1500, 1500, 3000, 11500, 1), 3: (2000, 3500, 5500, 12000, 2)}


def test_the_pdf_shows_balances_and_the_years_payouts(app, group, tmp_path):
    from app.services.pdf_service import PDFGenerator, _Styles

    _sync(group, _book(tmp_path, payouts=_PAYOUTS, summary=[(2025, 10000, None, None, None)]))
    data = PeriodStore.report_data(group.id, 2025, 3)

    _, balances = PDFGenerator._balance_section(data, _Styles.get())
    assert [row[0] for row in balances._cellvalues] == [
        '', 'Opening balance, 1 January 2025', 'Paid in', 'Money dispensed', 'Book balance, end of March 2025']
    assert balances._cellvalues[3][1:] == ['MWK 2,000.00', 'MWK 3,500.00']

    _, payouts = PDFGenerator._payouts_section(data, _Styles.get())
    assert [row[0] for row in payouts._cellvalues[1:]] == ['10 Feb 2025', '20 Mar 2025', '']
    assert payouts._cellvalues[-1][-1] == '3,500.00'
    assert PDFGenerator.generate_contribution_report_pdf(data)[:5] == b'%PDF-'


def test_report_previews_show_the_balances(client, group, make_user, login, tmp_path):
    make_user()
    login()
    _upload(client, _book(tmp_path, payouts=_PAYOUTS, summary=[(2025, 10000, None, None, None)]))

    page = client.get('/reports/preview').get_data(as_text=True)
    assert 'Money dispensed in 2025' in page and 'Ben Phiri' in page and '3,500' in page
    report = GeneratedReport.query.one()
    assert 'Money dispensed in 2025' in client.get(f'/reports/{report.id}').get_data(as_text=True)


def test_legacy_months_keep_the_sheets_own_figures(app, group, mzugoss_workbook):
    from app.services.excel_parser import ExcelParser

    PeriodStore.sync(group, ExcelParser.parse_excel(str(mzugoss_workbook), year=2026, month=3))
    data = PeriodStore.report_data(group.id, 2026, 3)
    assert 'dispensed_to_date' not in data


# ==================== SPREADSHEET SLIPS ====================

def test_a_typed_over_summary_formula_is_a_warning(app, group, tmp_path):
    run = _sync(group, _book(tmp_path, summary=[(2025, 10000, '=SUM(1)', 125000, '=B2+C2-D2')]))

    messages = _messages(run)
    assert any(m.startswith('Summary row 2, Payouts: Has a typed number (125,000) where the formula should be')
               for m in messages)
    assert not any(m.startswith(('Summary row 2, Opening', 'Summary row 2, Contributions',
                                 'Summary row 2, Closing')) for m in messages)


def test_dates_dragged_down_into_the_next_month_are_a_warning(app, group, tmp_path):
    members = [('M001', 'Ann Banda', date(2024, 1, 30), None),
               ('M002', 'Ben Phiri', date(2024, 1, 31), None),
               ('M003', 'Cara Mwale', date(2024, 2, 1), None),
               ('M004', 'Dan Zulu', date(2024, 3, 1), None),     # a fresh start: not part of the run
               ('M005', 'Eve Tembo', date(2024, 3, 2), None),
               ('M006', 'Fay Gondwe', date(2024, 3, 3), None)]   # counts up, but stays in March
    run = _sync(group, _book(tmp_path, members=members, contributions={}))

    dragged = [m for m in _messages(run) if 'dragged down' in m]
    assert len(dragged) == 1
    assert dragged[0].startswith('Members rows 2–4: Joined (month) goes up a day per row (30 Jan 2024, 31 Jan 2024')
    assert 'So rows 4–4 are in a later month than row 2.' in dragged[0]
