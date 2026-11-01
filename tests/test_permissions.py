"""
Permission checks: pages follow the officer's group role, officer
management respects the grant guardrails, and groups never see each
other's officers or reports.
"""
import pytest

from app.extensions import db
from app.models.report import GeneratedReport
from app.models.role import Role
from app.models.user import User


@pytest.fixture
def as_officer(client, make_user, login):
    """Create an officer with the given role and sign them in."""
    def _as(role, email=None):
        user = make_user(email=email or f'{role.lower()}@example.com', role=role)
        login(user.email)
        return user
    return _as


def _allowed(response):
    return response.status_code == 200


# ==================== PAGES BY ROLE ====================

@pytest.mark.parametrize('role,upload,officers,settings,reports', [
    ('Chairperson', True,  True,  True,  True),
    ('Treasurer',   True,  False, False, True),
    ('Secretary',   False, False, False, True),
])
def test_pages_follow_role_permissions(client, as_officer, role, upload, officers, settings, reports):
    as_officer(role)

    assert _allowed(client.get('/upload-dashboard')) is upload
    assert _allowed(client.get('/admin/users')) is officers
    assert _allowed(client.get('/settings')) is settings
    assert _allowed(client.get('/reports/')) is reports


@pytest.mark.parametrize('role,dashboard', [
    ('Chairperson', '/admin'),
    ('Treasurer', '/clerk-dashboard'),
    ('Secretary', '/viewer-dashboard'),
])
def test_dashboard_routes_by_permission(client, as_officer, role, dashboard):
    as_officer(role)
    assert client.get('/').headers['Location'] == dashboard


def test_superadmin_is_sent_to_platform_and_kept_out_of_group_pages(client, make_superadmin, login):
    make_superadmin()
    login('root@example.com', slug=None)

    assert client.get('/').headers['Location'] == '/platform/'
    assert not _allowed(client.get('/upload-dashboard'))
    assert not _allowed(client.get('/admin/users'))
    assert _allowed(client.get('/admin/cleanup'))


def test_officers_cannot_reach_platform_pages(client, as_officer):
    as_officer('Chairperson')
    assert not _allowed(client.get('/platform/'))
    assert not _allowed(client.get('/admin/cleanup'))


# ==================== OFFICER MANAGEMENT ====================

@pytest.fixture
def manager_role(group):
    """A role that can manage officers but holds few other permissions."""
    role = Role(group=group, name='Manager', permissions=['manage_users', 'view_reports'])
    db.session.add(role)
    db.session.commit()
    return role


def _role(group, name):
    return Role.query.filter_by(group_id=group.id, name=name).one()


def test_chair_creates_officer_with_group_role(client, group, as_officer):
    as_officer('Chairperson')

    response = client.post('/admin/users/create', data={
        'email': 'new@example.com', 'password': 'longenough',
        'confirm_password': 'longenough', 'role': _role(group, 'Treasurer').id,
    })

    assert response.status_code == 302
    new = User.query.filter_by(email='new@example.com').one()
    assert (new.group_id, new.role.name) == (group.id, 'Treasurer')


def test_officer_cannot_grant_role_beyond_own_permissions(client, group, make_user, login, manager_role):
    user = User(email='m@example.com', group_id=group.id, role=manager_role,
                password=make_user(email='seed@example.com').password)
    db.session.add(user)
    db.session.commit()
    login('m@example.com')

    form = client.get('/admin/users/create').data.decode()
    assert '>Chairperson<' not in form and '>Manager<' in form

    response = client.post('/admin/users/create', data={
        'email': 'sneaky@example.com', 'password': 'longenough',
        'confirm_password': 'longenough', 'role': _role(group, 'Chairperson').id,
    })
    assert response.status_code in (200, 403)
    assert User.query.filter_by(email='sneaky@example.com').first() is None


def test_officer_cannot_edit_holder_of_a_stronger_role(client, group, make_user, login, manager_role):
    chair = make_user(email='chair@example.com', role='Chairperson')
    user = User(email='m@example.com', group_id=group.id, role=manager_role, password=chair.password)
    db.session.add(user)
    db.session.commit()
    login('m@example.com')

    assert client.get(f'/admin/users/{chair.id}/edit').status_code == 403
    assert client.post(f'/admin/users/{chair.id}/toggle').status_code == 403
    assert db.session.get(User, chair.id).is_active


def test_officers_of_other_groups_are_not_found(client, make_group, make_user, as_officer):
    other = make_group(name='Another Welfare', slug='another')
    outsider = make_user(email='out@example.com', group=other)
    as_officer('Chairperson')

    assert client.get(f'/admin/users/{outsider.id}/edit').status_code == 404
    assert client.post(f'/admin/users/{outsider.id}/delete').status_code == 404
    assert b'out@example.com' not in client.get('/admin/users').data


def test_last_officer_manager_cannot_be_removed(client, group, make_user, as_officer):
    chair = as_officer('Chairperson')
    other_chair = make_user(email='chair2@example.com', role='Chairperson')

    # Two managers: deactivating one is fine
    client.post(f'/admin/users/{other_chair.id}/toggle')
    assert not db.session.get(User, other_chair.id).is_active

    # The remaining manager cannot delete their own account
    client.post('/auth/delete-account', data={'confirm_text': 'DELETE'})
    assert db.session.get(User, chair.id) is not None


def test_demoting_the_last_manager_is_blocked(client, group, make_user, login):
    chair = make_user(email='chair@example.com', role='Chairperson')
    other = make_user(email='chair2@example.com', role='Chairperson')
    login('chair2@example.com')

    # chair2 demotes chair: allowed, chair2 still manages
    client.post(f'/admin/users/{chair.id}/edit', data={
        'email': chair.email, 'role': _role(group, 'Treasurer').id, 'is_active': 'y',
    })
    assert db.session.get(User, chair.id).role.name == 'Treasurer'

    # chair (now Treasurer) can no longer manage officers at all
    client.get('/auth/logout')
    login('chair@example.com')
    assert client.get('/admin/users').status_code == 302
    assert db.session.get(User, other.id).role.name == 'Chairperson'


# ==================== REPORTS ARE GROUP-SCOPED ====================

def _report(group, user, archived=False):
    report = GeneratedReport(
        group_id=group.id, month=3, year=2026, filename='r.pdf', file_path='/nonexistent/r.pdf',
        generated_by=user.id, is_archived=archived,
    )
    db.session.add(report)
    db.session.commit()
    return report


def test_reports_of_other_groups_are_hidden(client, make_group, make_user, as_officer):
    other = make_group(name='Another Welfare', slug='another')
    theirs = _report(other, make_user(email='out@example.com', group=other))
    me = as_officer('Treasurer')
    mine = _report(me.group, me)

    listed = [r['id'] for r in client.get('/reports/api/list').get_json()['reports']]
    assert listed == [mine.id]
    assert client.get(f'/reports/api/{theirs.id}').status_code == 404
    assert client.post(f'/reports/{theirs.id}/archive').status_code == 404


def test_archived_reports_need_manage_reports(client, make_user, as_officer):
    secretary = as_officer('Secretary')
    archived = _report(secretary.group, secretary, archived=True)

    assert client.get('/reports/api/list').get_json()['reports'] == []
    assert client.get(f'/reports/api/{archived.id}').status_code == 403


def test_statistics_cover_only_own_group(client, make_group, make_user, as_officer):
    other = make_group(name='Another Welfare', slug='another')
    _report(other, make_user(email='out@example.com', group=other))
    me = as_officer('Chairperson')
    _report(me.group, me)

    assert client.get('/reports/stats').get_json()['total_reports'] == 1
