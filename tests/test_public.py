"""
A group's public pages for members (no accounts): home, the paid list behind
the group access code, and the name + PIN lookup with its lockouts.
"""
import re
from datetime import datetime, timedelta

import pandas as pd
import pytest

from app import create_app
from app.extensions import db
from app.models.group import Group, GroupSettings
from app.models.member import PARTIAL, Contribution, Member, MemberAlias, normalise_name
from app.services import member_service, public_access
from app.services.period_store import PeriodStore


def _sync(group, rows, month='March', year=2026, rate=None):
    PeriodStore.sync(group, {'data': pd.DataFrame(rows, columns=['Name', month]), 'name_col': 'Name',
                             'month_col': month, 'year': year, 'month': month}, rate=rate)


def _member(group, name):
    return Member.for_group(group.id).filter_by(normalised_name=normalise_name(name)).one()


@pytest.fixture
def march(group):
    """Ann paid, Ben part-paid (500 of 1,000), Cara didn't pay."""
    _sync(group, [('Ann Banda', 1000), ('Ben Phiri', 500), ('Cara Mwale', 0)], rate=1000)
    return group


def _enter_code(client, group, code=None):
    return client.post('/g/mzugoss/paid', data={'code': code or group.settings.access_code})


# ==================== HOME ====================

def test_home_page(client, march):
    page = client.get('/g/mzugoss/')
    html = page.data.decode()
    assert page.status_code == 200 and 'Mzugoss Class of 2018' in html
    assert '/g/mzugoss/rules' in html and '/g/mzugoss/paid' in html and '/g/mzugoss/check' in html
    assert 'Contributions last updated' in html
    assert page.headers['X-Robots-Tag'] == 'noindex, nofollow' and page.headers['Cache-Control'] == 'no-store'


def test_suspended_or_unknown_groups_have_no_pages(client, group):
    group.is_active = False
    db.session.commit()
    for path in ('/g/mzugoss/', '/g/mzugoss/paid', '/g/mzugoss/check', '/g/nope/'):
        assert client.get(path).status_code == 404, path


# ==================== ACCESS CODE ====================

def test_new_groups_get_an_access_code_that_is_on(app, group):
    assert group.settings.access_code_enabled
    assert len(group.settings.access_code) == 6 and not set(group.settings.access_code) & set('01OIL')


def test_paid_list_needs_the_code_once(client, march):
    assert b'Group code' in client.get('/g/mzugoss/paid').data
    assert b'Ann Banda' not in client.get('/g/mzugoss/paid').data

    wrong = client.post('/g/mzugoss/paid', data={'code': 'WRONG1'})
    assert b"That code isn't right" in wrong.data and b'Ann Banda' not in wrong.data

    code = march.settings.access_code
    shown = client.post('/g/mzugoss/paid', data={'code': f' {code.lower()[:3]} {code.lower()[3:]} '})
    assert b'Ann Banda' in shown.data
    assert b'Ann Banda' in client.get('/g/mzugoss/paid').data       # remembered


def test_code_for_one_group_does_not_open_another(client, march, make_group):
    other = make_group(name='Another Welfare', slug='another')
    _enter_code(client, march)
    assert b'Group code' in client.get('/g/another/paid').data


def test_with_the_code_off_the_list_is_open(client, march):
    march.settings.access_code_enabled = False
    db.session.commit()
    assert b'Ann Banda' in client.get('/g/mzugoss/paid').data


# ==================== PAID LIST ====================

def test_paid_list_never_shows_who_has_not_paid(client, march):
    page = _enter_code(client, march).data
    assert b'Ann Banda' in page
    assert b'Ben Phiri' not in page and b'Cara Mwale' not in page   # part paid and unpaid
    assert b'1,000' not in page                                       # amounts off by default


def test_amounts_and_totals_when_switched_on(client, march):
    march.settings.public_show_amounts = march.settings.public_show_totals = True
    db.session.commit()
    page = _enter_code(client, march).data.decode()
    assert 'MWK 1,000' in page            # Ann's amount
    assert 'members paid' in page and 'MWK 1,500' in page   # total received (incl. part payment)


def test_months_can_be_browsed_within_the_limit(client, march):
    _sync(march, [('Ann Banda', 1000)], month='January')
    _sync(march, [('Ann Banda', 1000), ('Ben Phiri', 1000)], month='February')
    march.settings.access_code_enabled = False
    march.settings.public_months_back = 2
    db.session.commit()

    assert b'March 2026' in client.get('/g/mzugoss/paid').data                 # latest by default
    feb = client.get('/g/mzugoss/paid?period=2026-2').data
    assert b'February 2026' in feb and b'Ben Phiri' in feb
    assert b'March 2026' in client.get('/g/mzugoss/paid?period=2026-1').data   # too old: latest instead
    assert b'March 2026' in client.get('/g/mzugoss/paid?period=junk').data


def test_paid_page_can_be_switched_off(client, march):
    march.settings.public_paid_enabled = False
    db.session.commit()
    assert client.get('/g/mzugoss/paid').status_code == 404
    assert b'/g/mzugoss/paid' not in client.get('/g/mzugoss/').data


def test_paid_list_shows_only_this_groups_members(client, march, make_group):
    other = make_group(name='Another Welfare', slug='another')
    _sync(other, [('Zed Theirs', 1000)])
    page = _enter_code(client, march).data
    assert b'Zed Theirs' not in page


# ==================== NAME + PIN LOOKUP ====================

@pytest.fixture
def ann_pin(march):
    return member_service.new_pin(_member(march, 'Ann Banda'))


def _check(client, name, pin, slug='mzugoss'):
    return client.post(f'/g/{slug}/check', data={'name': name, 'pin': pin})


FAILED = b"We couldn't find those details"


def test_lookup_shows_the_members_own_history(client, march, ann_pin):
    page = _check(client, '  ann   BANDA ', ann_pin)
    assert page.status_code == 200 and b'Your contributions' in page.data
    assert b'Ben Phiri' not in page.data
    assert page.headers['Cache-Control'] == 'no-store'


def test_every_failure_looks_the_same(client, march, ann_pin):
    member_service.new_pin(_member(march, 'Cara Mwale'))
    member_service.clear_pin(_member(march, 'Cara Mwale'))     # Cara has no PIN
    responses = [
        _check(client, 'Ann Banda', '000000' if ann_pin != '000000' else '111111'),   # wrong PIN
        _check(client, 'Nobody Here', ann_pin),                                       # unknown name
        _check(client, 'Cara Mwale', ann_pin),                                        # no PIN set
        _check(client, '', ann_pin),                                                  # no name
    ]
    assert all(FAILED in r.data for r in responses)
    # Apart from the per-request CSRF token, the pages are identical
    bodies = {re.sub(rb'name="csrf_token" value="[^"]*"', b'', r.data) for r in responses}
    assert len(bodies) == 1


def test_aliases_work_and_retired_members_do_not(client, march, ann_pin):
    ann = _member(march, 'Ann Banda')
    db.session.add(MemberAlias(group_id=march.id, member_id=ann.id, normalised_name='annie banda'))
    db.session.commit()
    assert b'Your contributions' in _check(client, 'Annie Banda', ann_pin).data

    ann.is_active = False
    db.session.commit()
    assert FAILED in _check(client, 'Ann Banda', ann_pin).data


def test_five_wrong_pins_lock_the_name_and_locks_grow(app, march, ann_pin):
    ann = _member(march, 'Ann Banda')
    wrong = '999999' if ann_pin != '999999' else '888888'

    for _ in range(public_access.MAX_FAILED):
        assert public_access.lookup(march, 'Ann Banda', wrong) is None
    assert ann.pin_lockouts == 1
    first_lock = ann.pin_locked_until - datetime.utcnow()
    assert timedelta(minutes=14) < first_lock <= timedelta(minutes=15)
    assert public_access.lookup(march, 'Ann Banda', ann_pin) is None      # right PIN, but locked

    ann.pin_locked_until = datetime.utcnow() - timedelta(seconds=1)       # the lock runs out
    db.session.commit()
    for _ in range(public_access.MAX_FAILED):
        public_access.lookup(march, 'Ann Banda', wrong)
    assert timedelta(minutes=29) < ann.pin_locked_until - datetime.utcnow() <= timedelta(minutes=30)

    ann.pin_locked_until = datetime.utcnow() - timedelta(seconds=1)
    db.session.commit()
    assert public_access.lookup(march, 'Ann Banda', ann_pin) == ann        # success resets
    assert (ann.pin_failed_attempts, ann.pin_lockouts) == (0, 0)


def test_lock_never_exceeds_a_day(app, march, ann_pin):
    ann = _member(march, 'Ann Banda')
    ann.pin_lockouts = 20
    ann.pin_failed_attempts = public_access.MAX_FAILED - 1
    db.session.commit()
    public_access.lookup(march, 'Ann Banda', 'x')
    assert ann.pin_locked_until - datetime.utcnow() <= timedelta(hours=24)


def test_officers_new_pin_unlocks(app, march, ann_pin):
    ann = _member(march, 'Ann Banda')
    ann.pin_locked_until = datetime.utcnow() + timedelta(hours=1)
    db.session.commit()
    pin = member_service.new_pin(ann)
    assert public_access.lookup(march, 'Ann Banda', pin) == ann


def test_public_forms_turn_off_autocomplete(client, march):
    for path in ('/g/mzugoss/check', '/g/mzugoss/paid'):
        assert b'autocomplete="off"' in client.get(path).data


# ==================== RATE LIMIT ====================

@pytest.fixture
def limited_client(tmp_path):
    app = create_app('testing', {
        'SQLALCHEMY_DATABASE_URI': 'sqlite://', 'RATELIMIT_ENABLED': True,
        'PUBLIC_LOOKUP_RATE_LIMIT': '3 per minute',
        'UPLOAD_FOLDER': str(tmp_path / 'u'), 'REPORT_FOLDER': str(tmp_path / 'r'), 'LOGS_FOLDER': str(tmp_path / 'l'),
    })
    with app.app_context():
        db.create_all()
        db.session.add(Group(name='G', slug='mzugoss', settings=GroupSettings(display_name='G')))
        db.session.commit()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def test_code_and_pin_attempts_share_a_rate_limit(limited_client):
    statuses = [
        limited_client.post('/g/mzugoss/check', data={'name': 'x', 'pin': '1'}).status_code,
        limited_client.post('/g/mzugoss/paid', data={'code': 'NOPE'}).status_code,
        limited_client.post('/g/mzugoss/check', data={'name': 'x', 'pin': '1'}).status_code,
        limited_client.post('/g/mzugoss/paid', data={'code': 'NOPE'}).status_code,
    ]
    assert statuses == [200, 200, 200, 429]
    assert limited_client.get('/g/mzugoss/check').status_code == 200    # reading isn't limited


# ==================== OFFICER SETTINGS ====================

@pytest.fixture
def chair(client, make_user, login):
    make_user(email='chair@example.com')
    login('chair@example.com')


def test_officers_manage_the_code_and_options(client, group, chair):
    old = group.settings.access_code
    assert old.encode() in client.get('/settings/public').data

    client.post('/settings/public', data={'action': 'new_code'})
    assert db.session.get(Group, group.id).settings.access_code != old

    client.post('/settings/public', data={'action': 'set_code', 'code': 'old boys 26'})
    assert db.session.get(Group, group.id).settings.access_code == 'OLDBOYS26'
    client.post('/settings/public', data={'action': 'set_code', 'code': 'a!'})
    assert db.session.get(Group, group.id).settings.access_code == 'OLDBOYS26'

    client.post('/settings/public', data={'action': 'toggle_code'})
    assert not db.session.get(Group, group.id).settings.access_code_enabled

    client.post('/settings/public', data={'action': 'options', 'public_paid_enabled': '1',
                                          'public_show_amounts': '1', 'public_months_back': '6'})
    s = db.session.get(Group, group.id).settings
    assert (s.public_paid_enabled, s.public_show_amounts, s.public_show_totals, s.public_months_back) == (
        True, True, False, 6)
    client.post('/settings/public', data={'action': 'options', 'public_months_back': '0'})
    assert db.session.get(Group, group.id).settings.public_months_back == 6


def test_public_settings_need_edit_settings(client, group, make_user, login):
    make_user(email='t@example.com', role='Treasurer')
    login('t@example.com')
    assert client.get('/settings/public').status_code != 200
