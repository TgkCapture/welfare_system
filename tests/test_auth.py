import pytest

from app import create_app
from app.controllers.auth_controller import LAST_GROUP_COOKIE, safe_next_url
from app.extensions import db


# ==================== GROUP LOGIN ====================

def test_officer_signs_in_on_own_group_page(client, make_user, login):
    make_user(email='chair@example.com')

    response = login('chair@example.com')

    assert response.status_code == 302
    assert response.headers['Location'] == '/'
    assert LAST_GROUP_COOKIE + '=mzugoss' in response.headers['Set-Cookie']


def test_officer_cannot_sign_in_on_another_groups_page(client, make_group, make_user, login):
    make_group(name='Another Welfare', slug='another')
    make_user(email='chair@example.com')

    response = login('chair@example.com', slug='another')

    assert response.headers['Location'].startswith('/g/another/login')
    assert client.get('/upload-dashboard').status_code == 302   # still anonymous


def test_same_email_signs_into_the_matching_groups_account(client, make_group, make_user, login):
    other = make_group(name='Another Welfare', slug='another')
    make_user(email='sam@example.com', password='mzugoss-pass')
    other_account = make_user(email='sam@example.com', password='another-pass',
                              group=other, role='Secretary')

    login('sam@example.com', password='another-pass', slug='another')

    with client.session_transaction() as sess:
        assert sess['_user_id'] == str(other_account.id)


def test_wrong_password_and_unknown_email_give_the_same_message(client, make_user, login):
    make_user(email='chair@example.com')

    for email, password in (('chair@example.com', 'wrong-pass'), ('nobody@example.com', 'secret123')):
        page = client.get(login(email, password=password).headers['Location'])
        assert b'Invalid email or password.' in page.data


def test_deactivated_officer_cannot_sign_in(client, make_user, login):
    make_user(email='gone@example.com', is_active=False)

    login('gone@example.com')

    assert client.get('/upload-dashboard').status_code == 302


def test_unknown_or_suspended_group_login_is_404(client, group):
    assert client.get('/g/nope/login').status_code == 404

    group.is_active = False
    db.session.commit()
    assert client.get('/g/mzugoss/login').status_code == 404


def test_suspending_a_group_signs_its_officers_out(client, group, make_user, login):
    make_user(email='chair@example.com')
    login('chair@example.com')
    assert client.get('/upload-dashboard').status_code == 200

    group.is_active = False
    db.session.commit()

    assert client.get('/upload-dashboard').status_code == 302


# ==================== PLATFORM LOGIN ====================

def test_superadmin_signs_in_on_platform_page(client, make_superadmin, login):
    make_superadmin(email='root@example.com')

    response = login('root@example.com', slug=None)

    assert response.headers['Location'] == '/platform/'
    assert client.get('/platform/').status_code == 200


def test_officer_cannot_use_platform_login(client, make_user, login):
    make_user(email='chair@example.com')

    login('chair@example.com', slug=None)

    assert client.get('/platform/').status_code == 302


def test_superadmin_cannot_use_a_group_login(client, make_superadmin, login, group):
    make_superadmin(email='root@example.com')

    login('root@example.com', slug='mzugoss')

    with client.session_transaction() as sess:
        assert '_user_id' not in sess


# ==================== GROUP FINDER & LOGOUT ====================

def test_finder_redirects_to_group_login(client, group):
    response = client.post('/auth/login', data={'group': ' Mzugoss '})
    assert response.headers['Location'] == '/g/mzugoss/login'


def test_finder_rejects_unknown_group(client, group):
    response = client.post('/auth/login', data={'group': 'nope'})
    assert response.status_code == 200
    assert b"couldn&#39;t find an active group" in response.data


def test_finder_remembers_last_group(client, group):
    client.set_cookie(LAST_GROUP_COOKIE, 'mzugoss')
    assert client.get('/auth/login').headers['Location'] == '/g/mzugoss/login'


def test_protected_page_sends_visitor_to_finder_with_next(client, group):
    response = client.get('/upload-dashboard')
    assert response.headers['Location'] == '/auth/login?next=/upload-dashboard'


def test_platform_page_sends_visitor_to_platform_login(client):
    response = client.get('/platform/')
    assert response.headers['Location'] == '/platform/login?next=/platform/'


def test_logout_returns_officer_to_group_login(client, make_user, login):
    make_user(email='chair@example.com')
    login('chair@example.com')

    assert client.get('/auth/logout').headers['Location'] == '/g/mzugoss/login'


def test_logout_returns_superadmin_to_platform_login(client, make_superadmin, login):
    make_superadmin(email='root@example.com')
    login('root@example.com', slug=None)

    assert client.get('/auth/logout').headers['Location'] == '/platform/login'


# ==================== OPEN REDIRECT ====================

@pytest.mark.parametrize('target,expected', [
    ('/reports/', '/reports/'),
    ('/upload-dashboard?x=1', '/upload-dashboard?x=1'),
    ('https://evil.example/', None),
    ('//evil.example/', None),
    ('/\\evil.example', None),
    ('javascript:alert(1)', None),
    ('evil.example', None),
    ('', None),
    (None, None),
])
def test_safe_next_url(target, expected):
    assert safe_next_url(target) == expected


def test_login_follows_local_next(client, make_user, login):
    make_user(email='chair@example.com')
    response = login('chair@example.com', next='/reports/')
    assert response.headers['Location'] == '/reports/'


def test_login_ignores_external_next(client, make_user, login):
    make_user(email='chair@example.com')
    response = login('chair@example.com', next='https://evil.example/')
    assert response.headers['Location'] == '/'


# ==================== RATE LIMITING ====================

@pytest.fixture
def limited_client(tmp_path):
    app = create_app('testing', {
        'SQLALCHEMY_DATABASE_URI': 'sqlite://',
        'RATELIMIT_ENABLED': True,
        'LOGIN_RATE_LIMIT': '3 per minute',
        'UPLOAD_FOLDER': str(tmp_path / 'u'), 'REPORT_FOLDER': str(tmp_path / 'r'),
        'LOGS_FOLDER': str(tmp_path / 'l'),
    })
    with app.app_context():
        from app.models.group import Group, GroupSettings
        db.create_all()
        g = Group(name='G', slug='mzugoss', settings=GroupSettings(display_name='G'))
        db.session.add(g)
        db.session.commit()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def test_login_attempts_are_rate_limited_across_login_pages(limited_client):
    attempt = {'email': 'x@example.com', 'password': 'wrong-pass'}
    statuses = [
        limited_client.post('/g/mzugoss/login', data=attempt).status_code,
        limited_client.post('/platform/login', data=attempt).status_code,
        limited_client.post('/g/mzugoss/login', data=attempt).status_code,
        limited_client.post('/platform/login', data=attempt).status_code,
    ]
    assert statuses == [302, 302, 302, 429]


def test_viewing_login_page_is_not_rate_limited(limited_client):
    assert all(limited_client.get('/g/mzugoss/login').status_code == 200 for _ in range(5))
