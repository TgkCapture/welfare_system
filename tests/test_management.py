"""
Management screens: superadmins manage groups on the platform pages, and
officers with manage_users edit their group's roles.
"""
import pathlib
import re

import pytest

from app.extensions import db
from app.models.group import Group
from app.models.role import Role
from app.models.user import User


def _role(group, name):
    return Role.query.filter_by(group_id=group.id, name=name).one()


# ==================== PLATFORM: GROUPS ====================

@pytest.fixture
def as_superadmin(client, make_superadmin, login):
    make_superadmin()
    login('root@example.com', slug=None)


_NEW_GROUP = {
    'name': 'Lilongwe Old Boys', 'slug': 'lob',
    'officer_email': 'chair@lob.example', 'officer_password': 'longenough',
    'confirm_password': 'longenough',
}


def test_superadmin_creates_group_with_first_chairperson(client, as_superadmin, login):
    response = client.post('/platform/groups/new', data=_NEW_GROUP)

    group = Group.query.filter_by(slug='lob').one()
    assert response.headers['Location'] == f'/platform/groups/{group.id}'
    assert group.settings.display_name == 'Lilongwe Old Boys'
    assert {r.name for r in Role.for_group(group.id)} == {'Chairperson', 'Treasurer', 'Secretary'}
    chair = User.for_group(group.id).one()
    assert (chair.email, chair.role.name) == ('chair@lob.example', 'Chairperson')

    # The new Chairperson can sign in on the group's page
    client.get('/auth/logout')
    login('chair@lob.example', password='longenough', slug='lob')
    assert client.get('/admin/users').status_code == 200


@pytest.mark.parametrize('slug', ['mzugoss', 'Bad Slug', 'trailing-', ''])
def test_group_slug_must_be_valid_and_unused(client, group, as_superadmin, slug):
    response = client.post('/platform/groups/new', data={**_NEW_GROUP, 'slug': slug})

    assert response.status_code == 200
    assert Group.query.count() == 1


def test_superadmin_suspends_and_reactivates_group(client, group, as_superadmin):
    client.post(f'/platform/groups/{group.id}/toggle')
    assert db.session.get(Group, group.id).is_active is False
    assert client.get('/g/mzugoss/login').status_code == 404

    client.post(f'/platform/groups/{group.id}/toggle')
    assert db.session.get(Group, group.id).is_active is True


def test_renaming_a_group_keeps_its_slug(client, group, as_superadmin):
    client.post(f'/platform/groups/{group.id}', data={'name': 'Mzugoss Welfare', 'slug': 'hijack'})

    group = db.session.get(Group, group.id)
    assert (group.name, group.slug) == ('Mzugoss Welfare', 'mzugoss')


def test_superadmin_adds_officer_to_a_locked_out_group(client, group, make_user, as_superadmin):
    make_user(email='gone@example.com', is_active=False)

    client.post(f'/platform/groups/{group.id}/officers', data={
        'email': 'rescue@example.com', 'password': 'longenough',
        'confirm_password': 'longenough', 'role': _role(group, 'Chairperson').id,
    })

    rescue = User.for_group(group.id).filter_by(email='rescue@example.com').one()
    assert rescue.role.name == 'Chairperson' and rescue.is_active


def test_platform_officer_email_is_unique_within_the_target_group(client, group, make_group,
                                                                  make_user, as_superadmin):
    other = make_group(name='Another Welfare', slug='another')
    make_user(email='sam@example.com')

    def add(target):
        client.post(f'/platform/groups/{target.id}/officers', data={
            'email': 'sam@example.com', 'password': 'longenough',
            'confirm_password': 'longenough', 'role': _role(target, 'Secretary').id,
        })

    add(group)    # taken in this group
    add(other)    # free in the other group
    assert User.for_group(group.id).filter_by(email='sam@example.com').count() == 1
    assert User.for_group(other.id).filter_by(email='sam@example.com').count() == 1


def test_platform_cannot_assign_another_groups_role(client, group, make_group, as_superadmin):
    other = make_group(name='Another Welfare', slug='another')

    response = client.post(f'/platform/groups/{group.id}/officers', data={
        'email': 'x@example.com', 'password': 'longenough',
        'confirm_password': 'longenough', 'role': _role(other, 'Chairperson').id,
    })

    assert response.status_code in (302, 400)
    assert User.query.filter_by(email='x@example.com').first() is None


def test_platform_group_pages_are_superadmin_only(client, group, make_user, login):
    make_user(email='chair@example.com')
    login('chair@example.com')

    assert client.get(f'/platform/groups/{group.id}').status_code != 200
    assert client.post(f'/platform/groups/{group.id}/toggle').status_code != 200
    assert client.post('/platform/groups/new', data=_NEW_GROUP).status_code != 200
    assert db.session.get(Group, group.id).is_active
    assert Group.query.filter_by(slug='lob').first() is None


def test_unknown_group_is_404(client, as_superadmin):
    assert client.get('/platform/groups/999').status_code == 404


# ==================== GROUP ROLES ====================

@pytest.fixture
def chair(client, make_user, login):
    user = make_user(email='chair@example.com')
    login('chair@example.com')
    return user


def test_chair_creates_a_custom_role(client, group, chair):
    response = client.post('/admin/roles/create', data={
        'name': ' Auditor ', 'permissions': ['view_reports', 'generate_reports'],
    })

    assert response.headers['Location'] == '/admin/roles'
    role = _role(group, 'Auditor')
    assert role.permissions == ['generate_reports', 'view_reports']   # display order


def test_role_names_are_unique_within_a_group(client, group, make_group, chair):
    make_group(name='Another Welfare', slug='another')   # has its own "Treasurer"

    client.post('/admin/roles/create', data={'name': 'Treasurer', 'permissions': ['view_reports']})
    assert Role.for_group(group.id).filter_by(name='Treasurer').count() == 1


def test_chair_edits_a_role_and_its_holders_follow(client, group, make_user, chair):
    treasurer = make_user(email='t@example.com', role='Treasurer')
    role = _role(group, 'Treasurer')

    client.post(f'/admin/roles/{role.id}/edit', data={
        'name': 'Finance Officer', 'permissions': ['view_reports'],
    })

    role = db.session.get(Role, role.id)
    assert (role.name, role.permissions) == ('Finance Officer', ['view_reports'])
    assert not db.session.get(User, treasurer.id).has_permission('upload_data')


def test_role_cannot_get_permissions_the_editor_lacks(client, group, make_user, login):
    manager = Role(group=group, name='Manager', permissions=['manage_users', 'view_reports'])
    db.session.add(manager)
    db.session.commit()
    make_user(email='m@example.com', role='Manager')
    login('m@example.com')

    # Not offered, and rejected if submitted anyway
    assert b'edit_settings' not in client.get('/admin/roles/create').data
    client.post('/admin/roles/create', data={'name': 'Boss', 'permissions': ['edit_settings']})
    assert Role.for_group(group.id).filter_by(name='Boss').first() is None

    # Can't escalate their own role either
    client.post(f'/admin/roles/{manager.id}/edit', data={
        'name': 'Manager', 'permissions': ['manage_users', 'view_reports', 'edit_settings'],
    })
    assert db.session.get(Role, manager.id).permissions == ['manage_users', 'view_reports']

    # Roles with permissions they lack are off limits
    chairperson = _role(group, 'Chairperson')
    assert client.get(f'/admin/roles/{chairperson.id}/edit').status_code == 403
    assert client.post(f'/admin/roles/{chairperson.id}/delete').status_code == 403


def test_removing_manage_users_from_the_last_managers_role_is_blocked(client, group, chair):
    role = _role(group, 'Chairperson')

    client.post(f'/admin/roles/{role.id}/edit', data={
        'name': 'Chairperson', 'permissions': ['view_reports'],
    })

    assert db.session.get(Role, role.id).has('manage_users')


def test_removing_manage_users_is_fine_when_another_role_still_manages(client, group, make_user, login):
    make_user(email='chair@example.com')
    admin_role = Role(group=group, name='Admin', permissions=['manage_users'])
    db.session.add(admin_role)
    db.session.commit()
    make_user(email='admin@example.com', role='Admin')
    login('chair@example.com')

    client.post(f'/admin/roles/{admin_role.id}/edit', data={'name': 'Admin', 'permissions': []})

    assert db.session.get(Role, admin_role.id).permissions == []


def test_a_role_in_use_cannot_be_deleted(client, group, make_user, chair):
    make_user(email='t@example.com', role='Treasurer')
    treasurer_id, secretary_id = _role(group, 'Treasurer').id, _role(group, 'Secretary').id

    client.post(f'/admin/roles/{treasurer_id}/delete')
    client.post(f'/admin/roles/{secretary_id}/delete')

    remaining = {r.id for r in Role.for_group(group.id)}
    assert treasurer_id in remaining and secretary_id not in remaining


def test_roles_pages_need_manage_users(client, group, make_user, login):
    make_user(email='t@example.com', role='Treasurer')
    login('t@example.com')

    assert client.get('/admin/roles').status_code != 200
    assert client.post('/admin/roles/create', data={'name': 'X'}).status_code != 200
    assert Role.for_group(group.id).filter_by(name='X').first() is None


# ==================== CSRF ====================

_TEMPLATES = pathlib.Path(__file__).resolve().parent.parent / 'app' / 'templates'


def test_every_post_form_carries_a_csrf_token():
    """CSRF is off under test, so a form without a token would only fail in production."""
    missing = []
    for path in _TEMPLATES.rglob('*.html'):
        text = path.read_text(encoding='utf-8')
        for m in re.finditer(r'<form\b([^>]*)>(.*?)</form>', text, re.S | re.I):
            if 'post' in m.group(1).lower() and not re.search(r'csrf_token\(\)|hidden_tag\(\)', m.group(2)):
                missing.append(f'{path.relative_to(_TEMPLATES)}:{text[:m.start()].count(chr(10)) + 1}')
    assert missing == []
