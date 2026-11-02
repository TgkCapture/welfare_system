"""
The standard workbook: the template the app generates, reading and syncing
it, the checks a sync runs, and the pages around it.
"""
from datetime import date, timedelta

import pytest
from openpyxl import load_workbook

from app.extensions import db
from app.models.ledger import Payout, PayoutPurpose, Rate, SyncRun, YearSummary
from app.models.member import PAID, PARTIAL, UNPAID, Contribution, Member, MemberAlias, PeriodSummary
from app.models.report import GeneratedReport
from app.services.standard_sync import StandardSync
from app.services.standard_workbook import StandardWorkbook
from app.services.workbook_template import build_template
from tests.workbooks import build_standard_workbook

MEMBERS = [
    ('M001', 'Ann Banda', date(2024, 1, 1), None),
    ('M002', 'Ben Phiri', date(2024, 1, 1), None),
    ('M003', 'Cara Mwale', date(2025, 3, 1), None),    # joins March 2025
]


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


def test_member_missing_from_a_years_sheet_is_unpaid_with_a_warning(app, group, tmp_path):
    run = _sync(group, _book(tmp_path, contributions={2025: [('M001', 'Ann Banda', {'January': 1000})]}))

    assert _month(group, 2025, 1) == {'Ann Banda': (1000, PAID), 'Ben Phiri': (0, UNPAID)}
    assert any('M002 Ben Phiri is a member in 2025 but has no row' in m for m in _messages(run))


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


def test_purposes_are_per_group_and_need_edit_settings(client, group, make_group, make_user, login):
    other = make_group(name='Another Welfare', slug='another')
    theirs = PayoutPurpose.for_group(other.id).first()
    make_user(email='t@example.com', role='Treasurer')
    make_user(email='chair@example.com')

    login('t@example.com')
    assert client.get('/settings/payout-purposes').status_code != 200
    client.get('/auth/logout')
    login('chair@example.com')
    assert client.post(f'/settings/payout-purposes/{theirs.id}/toggle').status_code == 404
    assert db.session.get(PayoutPurpose, theirs.id).is_active
