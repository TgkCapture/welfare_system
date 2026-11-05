"""
The monthly cycle: choose the month and source, then check what the sync
found (new names to merge, warnings) and share the result.
"""
from datetime import date

import pandas as pd
import pytest

from app.controllers.upload_controller import UploadController
from app.extensions import db
from app.models.member import Member, PeriodSummary, normalise_name
from app.services.period_store import PeriodStore
from tests.workbooks import build_standard_workbook


def _sync(group, rows, month='March', year=2026):
    PeriodStore.sync(group, {'data': pd.DataFrame(rows, columns=['Name', month]), 'name_col': 'Name',
                             'month_col': month, 'year': year, 'month': month})


def _upload(client, path, month='3', year='2026'):
    with open(path, 'rb') as fh:
        return client.post('/upload', data={'file': (fh, 'book.xlsx'), 'year': year, 'month': month},
                           content_type='multipart/form-data')


@pytest.fixture
def chair(client, make_user, login):
    user = make_user(email='chair@example.com')
    login('chair@example.com')
    return user


# ==================== STEP 1: CHOOSE ====================

@pytest.mark.parametrize('latest,now,expected', [
    (None, (2026, 5), (2026, 5)),               # nothing synced: this month
    ((2026, 3), (2026, 11), (2026, 4)),         # the month after the last one
    ((2025, 12), (2026, 11), (2026, 1)),        # over the new year
    ((2026, 11), (2026, 11), (2026, 11)),       # never a month still to come
])
def test_suggested_month(monkeypatch, latest, now, expected):
    class FakeNow:
        @staticmethod
        def now():
            return date(*now, 1)
    monkeypatch.setattr('app.controllers.upload_controller.datetime', FakeNow)
    summary = PeriodSummary(year=latest[0], month=latest[1]) if latest else None
    assert UploadController._suggested_month(summary) == expected


def test_upload_page_says_what_was_last_synced(client, group, chair):
    _sync(group, [('Ann', 1000)], month='February')
    page = client.get('/upload-dashboard').data.decode()
    assert 'Last month synced: February 2026' in page
    assert 'Read the workbook' in page


# ==================== STEP 2: CHECK ====================

@pytest.fixture
def uploaded(client, group, chair, tmp_path):
    """Ann exists; the workbook brings 'Anne Banda' (a respelling) and a genuinely new member."""
    _sync(group, [('Ann Banda', 1000)], month='January')
    path = build_standard_workbook(
        tmp_path / 'book.xlsx',
        [('M001', 'Anne Banda', None, None), ('M002', 'Zed Newcomer', None, None)],
        {2026: [('M001', 'Anne Banda', {'March': 1000}), ('M002', 'Zed Newcomer', {'March': 0})]},
        payouts=[(date(2026, 3, 5), 'M009', None, 'Party', 100, 'Chair')],
        summary=[(2026, 0, None, None, None)],
    )
    assert _upload(client, path).headers['Location'] == '/reports/preview'
    return group


def test_check_page_lists_new_names_with_likely_matches(client, uploaded):
    page = client.get('/reports/preview').data.decode()
    assert 'New names (2)' in page
    assert 'Same as Ann Banda' in page                       # suggested for "Anne Banda"
    assert 'No similar names: probably a new member' in page  # for "Zed Newcomer"
    assert 'Warnings from the workbook' in page and 'M009' in page


def test_merging_in_place_with_htmx(client, uploaded):
    anne = Member.for_group(uploaded.id).filter_by(normalised_name='anne banda').one()
    ann = Member.for_group(uploaded.id).filter_by(normalised_name='ann banda').one()

    response = client.post(f'/members/{anne.id}/merge', data={'into': ann.id}, headers={'HX-Request': 'true'})

    assert response.status_code == 200 and b'merged into' in response.data
    assert b'<html' not in response.data                    # a fragment, not a page
    assert Member.for_group(uploaded.id).filter_by(normalised_name='anne banda').first() is None


def test_inline_merge_errors_stay_inline(client, uploaded):
    anne = Member.for_group(uploaded.id).filter_by(normalised_name='anne banda').one()
    response = client.post(f'/members/{anne.id}/merge', data={'into': ''}, headers={'HX-Request': 'true'})
    assert response.status_code == 200 and b'Choose the member to merge into' in response.data


def test_new_names_need_manage_members(client, group, make_user, login, tmp_path, uploaded):
    client.get('/auth/logout')
    make_user(email='sec@example.com', role='Secretary')     # can view reports, not manage members
    login('sec@example.com')
    with client.session_transaction() as sess:                 # the Secretary didn't upload anything
        assert 'last_run_id' not in sess


def test_nothing_to_check(client, group, chair, mzugoss_workbook):
    _sync(group, [(n, 0) for n in ('Alinafe Banda', 'Bright Phiri', 'Chisomo Mwale', 'Dumisani Zulu',
                                   'Esther Tembo', 'Fañny Kumwenda', 'Gift Nyirenda')], month='January')
    with open(mzugoss_workbook, 'rb') as fh:
        client.post('/upload', data={'file': (fh, 'm.xlsx'), 'year': '2026', 'month': '3'},
                    content_type='multipart/form-data')
    page = client.get('/reports/preview').data.decode()
    assert 'New names' not in page
    # The old layout's text cell ("pending") is the only warning
    assert 'Warnings from the workbook (1)' in page


# ==================== STEP 3: SHARE ====================

def test_share_message_has_the_paid_link_and_code(client, uploaded):
    page = client.get('/reports/preview').data.decode()
    code = uploaded.settings.access_code
    assert '/g/mzugoss/paid?period=2026-3' in page
    assert f'Group code: {code}' in page
    assert '/g/mzugoss/check' in page
    assert 'wa.me/?text=' in page


def test_share_without_the_paid_page_or_code(client, uploaded):
    uploaded.settings.access_code_enabled = False
    db.session.commit()
    assert 'Group code:' not in client.get('/reports/preview').data.decode()

    uploaded.settings.public_paid_enabled = False
    db.session.commit()
    page = client.get('/reports/preview').data.decode()
    assert 'See who has paid' not in page and 'page is off' in page
