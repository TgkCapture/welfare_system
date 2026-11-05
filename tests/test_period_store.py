"""
Stored contribution data: each sync stores the month's members,
contributions and summary, and reports read them back from the DB
instead of from the session cookie.
"""
import pandas as pd
import pytest

from app.extensions import db
from app.models.member import (
    PAID, PARTIAL, UNPAID, Contribution, Member, MemberAlias, PeriodSummary, normalise_name,
)
from app.models.report import GeneratedReport
from app.models.tenancy import TenantScoped
from app.services.period_store import PeriodStore, status_for


def _parsed(rows, year=2026, month='March', **financial):
    """ExcelParser-shaped output for a list of (name, amount) rows."""
    return {
        'data': pd.DataFrame(rows, columns=['Name', month]),
        'name_col': 'Name', 'month_col': month, 'year': year, 'month': month,
        **financial,
    }


def _upload(client, workbook, month='3'):
    with open(workbook, 'rb') as fh:
        return client.post(
            '/upload',
            data={'file': (fh, 'mzugoss.xlsx'), 'year': '2026', 'month': month},
            content_type='multipart/form-data',
        )


def _amounts(group, year=2026, month=3):
    return {
        c.member.display_name: (c.amount, c.status)
        for c in Contribution.for_group(group.id).filter_by(year=year, month=month)
    }


# ==================== NAMES AND STATUS ====================

@pytest.mark.parametrize('a,b', [
    ('Gift  Nyirenda', 'gift nyirenda'),
    (' Alinafe Banda ', 'ALINAFE BANDA'),
    ('J. Banda', 'j banda'),
    ('Fañny Kumwenda', 'FAÑNY KUMWENDA'),
])
def test_normalise_name_ignores_case_spacing_and_dots(a, b):
    assert normalise_name(a) == normalise_name(b)


@pytest.mark.parametrize('amount,rate,status', [
    (1000, None, PAID), (500, None, PAID), (0, None, UNPAID), (None, None, UNPAID),
    (-50, None, UNPAID), (1000, 1000, PAID), (1500, 1000, PAID), (500, 1000, PARTIAL),
])
def test_status_for(amount, rate, status):
    assert status_for(amount, rate) == status


# ==================== SYNC ====================

def test_upload_stores_the_month(client, group, make_user, login, mzugoss_workbook):
    make_user()
    login()

    assert _upload(client, mzugoss_workbook).status_code == 302

    summary = PeriodSummary.for_group(group.id).one()
    assert (summary.year, summary.month, summary.source) == (2026, 3, 'upload')
    assert (summary.total_contributions, summary.contributors_count, summary.defaulters_count) == (2500, 3, 4)
    assert (summary.money_dispensed, summary.book_balance) == (30000, 150000.50)

    assert _amounts(group) == {
        'Alinafe Banda': (1000, PAID), 'Bright Phiri': (500, PAID),
        'Chisomo Mwale': (0, UNPAID), 'Dumisani Zulu': (0, UNPAID),
        'Esther Tembo': (0, UNPAID), 'Fañny Kumwenda': (1000, PAID),
        'Gift Nyirenda': (0, UNPAID),   # double space tidied
    }
    # The report record matches the stored summary
    report = GeneratedReport.query.one()
    assert (report.total_contributions, report.contributors_count, report.defaulters_count) == (2500, 3, 4)


def test_resync_replaces_the_month_and_keeps_others(app, group):
    PeriodStore.sync(group, _parsed([('Ann', 1000), ('Ben', 0)], month='February'))
    PeriodStore.sync(group, _parsed([('Ann', 1000), ('Ben', 0)]))

    PeriodStore.sync(group, _parsed([('Ann', 1000), ('Ben', 1000)]))   # Ben paid late

    assert _amounts(group) == {'Ann': (1000, PAID), 'Ben': (1000, PAID)}
    assert Contribution.for_group(group.id).filter_by(month=2).count() == 2
    assert Member.for_group(group.id).count() == 2
    assert PeriodSummary.for_group(group.id).filter_by(month=3).one().contributors_count == 2


def test_rows_dropped_from_the_sheet_are_dropped_from_the_month(app, group):
    PeriodStore.sync(group, _parsed([('Ann', 1000), ('Ben', 1000)]))
    PeriodStore.sync(group, _parsed([('Ann', 1000)]))

    assert _amounts(group) == {'Ann': (1000, PAID)}
    assert Member.for_group(group.id).count() == 2   # members are never deleted by a sync


def test_respellings_match_the_same_member(app, group):
    PeriodStore.sync(group, _parsed([('Gift  Nyirenda', 1000)], month='February'))

    result = PeriodStore.sync(group, _parsed([('gift nyirenda', 500)]))

    assert result['new_members'] == []
    member = Member.for_group(group.id).one()
    assert member.display_name == 'Gift Nyirenda'   # first spelling kept
    assert member.contributions.count() == 2


def test_aliases_match_the_member(app, group):
    member = Member(group_id=group.id, display_name='Chisomo Mwale', normalised_name='chisomo mwale')
    db.session.add(member)
    db.session.flush()
    db.session.add(MemberAlias(group_id=group.id, member_id=member.id, normalised_name='chiso mwale'))
    db.session.commit()

    result = PeriodStore.sync(group, _parsed([('Chiso Mwale', 1000)]))

    assert result['new_members'] == []
    assert _amounts(group) == {'Chisomo Mwale': (1000, PAID)}


def test_new_names_are_reported(app, group):
    first = PeriodStore.sync(group, _parsed([('Ann', 1000), ('Ben', 0)]))
    second = PeriodStore.sync(group, _parsed([('Ann', 1000), ('Ben', 0), ('Cara', 500)]))

    assert first['new_members'] == ['Ann', 'Ben']
    assert second['new_members'] == ['Cara']


def test_a_name_listed_twice_is_added_up_and_reported(app, group):
    result = PeriodStore.sync(group, _parsed([('Ann', 500), ('ann', 500), ('Ben', 0)]))

    assert result['repeated_names'] == ['ann']
    assert _amounts(group) == {'Ann': (1000, PAID), 'Ben': (0, UNPAID)}
    summary = result['summary']
    assert (summary.contributors_count, summary.defaulters_count) == (1, 1)


def test_a_known_rate_marks_partial_payments(app, group):
    PeriodStore.sync(group, _parsed([('Ann', 1000), ('Ben', 500)]), rate=1000)

    assert _amounts(group) == {'Ann': (1000, PAID), 'Ben': (500, PARTIAL)}
    assert PeriodStore.paid_members(group.id, 2026, 3)[1]['status'] == 'Partial'


def test_groups_keep_separate_members(app, group, make_group):
    other = make_group(name='Another Welfare', slug='another')
    PeriodStore.sync(group, _parsed([('Ann', 1000)]))

    result = PeriodStore.sync(other, _parsed([('Ann', 0)]))

    assert result['new_members'] == ['Ann']
    assert _amounts(group) == {'Ann': (1000, PAID)}
    assert _amounts(other) == {'Ann': (0, UNPAID)}


# ==================== READING BACK ====================

def test_report_data_round_trips(app, group):
    PeriodStore.sync(group, _parsed([('Ann', 1000), ('Ben', 0), ('Cara', 500)],
                                    money_dispensed=200.0, total_book_balance=900.0))

    data = PeriodStore.report_data(group.id, 2026, 3)

    assert list(data['data']['Name']) == ['Ann', 'Ben', 'Cara']   # sheet order
    assert (data['month'], data['year'], data['month_col']) == ('March', 2026, 'March')
    assert (data['total_contributions'], data['num_contributors'], data['num_missing']) == (1500, 2, 1)
    assert data['defaulters'] == ['Ben']
    assert (data['money_dispensed'], data['total_book_balance']) == (200.0, 900.0)
    assert PeriodStore.report_data(group.id, 2026, 4) is None


def test_session_cookie_holds_no_member_data(client, make_user, login, mzugoss_workbook):
    make_user()
    login()
    _upload(client, mzugoss_workbook)

    with client.session_transaction() as sess:
        assert 'report_data' not in sess and 'report_path' not in sess
        assert sess['last_report_id'] == GeneratedReport.query.one().id


def test_preview_download_and_paid_members_after_upload(client, make_user, login, mzugoss_workbook):
    make_user()
    login()
    _upload(client, mzugoss_workbook)
    report_id = GeneratedReport.query.one().id

    assert client.get('/reports/preview').status_code == 200
    assert client.get('/reports/download').mimetype == 'application/pdf'
    page = client.get('/reports/paid-members')
    assert b'Alinafe Banda' in page.data and b'Chisomo' not in page.data
    assert client.get('/reports/paid-members/download').mimetype == 'image/png'

    # The same detail is available later from the report itself
    assert b'Fa\xc3\xb1ny Kumwenda' in client.get(f'/reports/{report_id}/paid-members').data
    assert client.get(f'/reports/paid-members/download/{report_id}').mimetype == 'image/png'


def test_report_from_before_stored_data_explains_itself(client, group, make_user, login):
    user = make_user()
    report = GeneratedReport(group_id=group.id, month=1, year=2025, filename='old.pdf',
                             file_path='/nonexistent/old.pdf', generated_by=user.id)
    db.session.add(report)
    db.session.commit()
    login()

    response = client.get(f'/reports/{report.id}/paid-members')

    assert response.headers['Location'] == f'/reports/{report.id}'
    page = client.get(response.headers['Location'])
    assert b"isn&#39;t stored yet" in page.data


def test_every_tenant_model_is_covered_by_the_static_guard():
    from tests.test_tenancy import _TENANT_MODELS
    guarded = set(_TENANT_MODELS.strip('(?:)').split('|'))
    assert {cls.__name__ for cls in TenantScoped.__subclasses__()} == guarded
