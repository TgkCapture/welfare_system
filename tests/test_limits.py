"""
Rate limits on everything that checks a secret: only failed attempts count,
per client IP, and the client's own address is used behind a trusted proxy.
"""
import pandas as pd
import pytest

from app import create_app
from app.extensions import db
from app.models.audit import AuditEvent
from app.models.member import Member
from app.services import member_service
from app.services.period_store import PeriodStore
from tests.conftest import TEST_DATABASE_URL, FreshContextClient


@pytest.fixture
def app(tmp_path, request):
    """Limits on, three failures a minute; parametrize indirectly for other settings."""
    app = create_app('testing', {
        'SQLALCHEMY_DATABASE_URI': TEST_DATABASE_URL, 'RATELIMIT_ENABLED': True,
        'RATELIMIT_STORAGE_URI': 'memory://',
        'LOGIN_RATE_LIMIT': '3 per minute', 'PUBLIC_LOOKUP_RATE_LIMIT': '3 per minute',
        'UPLOAD_FOLDER': str(tmp_path / 'u'), 'REPORT_FOLDER': str(tmp_path / 'r'),
        'LOGS_FOLDER': str(tmp_path / 'l'), 'BRANDING_FOLDER': str(tmp_path / 'b'),
        **getattr(request, 'param', {}),
    })
    app.test_client_class = FreshContextClient
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def ann(group):
    PeriodStore.sync(group, {'data': pd.DataFrame([('Ann Banda', 1000)], columns=['Name', 'March']),
                             'name_col': 'Name', 'month_col': 'March', 'year': 2026, 'month': 'March'})
    member = Member.for_group(group.id).one()
    pin = member_service.new_pin(member)
    db.session.commit()
    return member, pin


# ==================== SIGN-IN ====================

def test_successful_sign_ins_do_not_use_up_the_budget(client, group, make_user, login):
    make_user(email='chair@example.com')
    for _ in range(5):
        assert login('chair@example.com').headers['Location'] == '/'
        client.get('/auth/logout')


def test_failed_sign_ins_lock_out_the_address_even_with_the_right_password(client, group, make_user, login):
    make_user(email='chair@example.com')
    statuses = [login('chair@example.com', password='wrong-pass').status_code for _ in range(3)]
    assert statuses == [302, 302, 302]
    assert login('chair@example.com').status_code == 429
    assert client.get('/g/mzugoss/login').status_code == 200     # the page still opens


def test_wrong_current_passwords_count_against_sign_in(client, group, make_user, login):
    make_user(email='chair@example.com')
    login('chair@example.com')
    attempt = {'current_password': 'guess', 'new_password': 'n3w-password', 'confirm_password': 'n3w-password'}

    assert [client.post('/auth/change-password', data=attempt).status_code for _ in range(3)] == [302] * 3
    assert client.post('/auth/change-password', data=attempt).status_code == 429


def test_unknown_group_codes_count_against_sign_in(client, group):
    assert all(client.post('/auth/login', data={'group': 'mzugoss'}).status_code == 302 for _ in range(4))
    assert [client.post('/auth/login', data={'group': 'nope'}).status_code for _ in range(4)] == [200] * 3 + [429]


# ==================== PUBLIC LOOKUPS ====================

def test_right_pins_do_not_use_up_the_budget(client, group, ann):
    member, pin = ann
    for _ in range(5):
        assert b'Ann Banda' in client.post('/g/mzugoss/check', data={'name': 'Ann Banda', 'pin': pin}).data


def test_wrong_history_links_count_against_the_lookup_budget(client, group, ann):
    member, pin = ann
    right = f'/g/mzugoss/m/{member.history_token}'

    assert all(client.get(right).status_code == 200 for _ in range(4))
    assert client.get('/g/mzugoss/m/guess-1').status_code == 404
    assert client.post('/g/mzugoss/check', data={'name': 'Ann Banda', 'pin': '000000'}).status_code == 200
    assert client.post('/g/mzugoss/paid', data={'code': 'NOPE'}).status_code == 200
    assert client.get('/g/mzugoss/m/guess-2').status_code == 429
    assert client.get(right).status_code == 429


# ==================== BEHIND A PROXY ====================

@pytest.mark.parametrize('app', [{'TRUSTED_PROXIES': 1}], indirect=True)
def test_behind_a_trusted_proxy_each_visitor_has_their_own_budget(client, group, make_user, login):
    make_user(email='chair@example.com')
    attempt = {'email': 'chair@example.com', 'password': 'wrong-pass'}

    def post(ip):
        return client.post('/g/mzugoss/login', data=attempt, headers={'X-Forwarded-For': ip}).status_code

    assert [post('10.0.0.1') for _ in range(4)] == [302] * 3 + [429]
    assert post('10.0.0.2') == 302
    assert {e.ip_address for e in AuditEvent.query.all()} == {'10.0.0.1', '10.0.0.2'}


def test_without_a_trusted_proxy_forwarded_addresses_are_ignored(client, group, make_user, login):
    make_user(email='chair@example.com')
    attempt = {'email': 'chair@example.com', 'password': 'wrong-pass'}

    for ip in ('10.0.0.1', '10.0.0.2', '10.0.0.3'):
        client.post('/g/mzugoss/login', data=attempt, headers={'X-Forwarded-For': ip})

    assert client.post('/g/mzugoss/login', data=attempt, headers={'X-Forwarded-For': '10.0.0.4'}).status_code == 429
    assert {e.ip_address for e in AuditEvent.query.all()} == {'127.0.0.1'}
