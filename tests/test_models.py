import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.group import Group
from app.models.role import PERMISSIONS, PRESET_ROLES, Role
from app.models.user import User


def test_new_group_gets_preset_roles(group):
    roles = {r.name: r for r in group.roles}
    assert set(roles) == set(PRESET_ROLES)
    assert set(roles['Chairperson'].permissions) == set(PERMISSIONS)
    assert roles['Treasurer'].has('upload_data')
    assert not roles['Secretary'].has('manage_users')


def test_permissions_come_from_group_role(make_user, make_superadmin):
    chair = make_user(email='chair@example.com', role='Chairperson')
    secretary = make_user(email='sec@example.com', role='Secretary')
    root = make_superadmin()

    assert chair.has_permission('manage_users')
    assert secretary.has_permission('edit_rules')
    assert not secretary.has_permission('upload_data')
    assert root.permissions == frozenset()
    assert (chair.role_name, root.role_name) == ('Chairperson', 'Superadmin')


def test_can_grant_only_roles_within_own_permissions(group, make_user):
    roles = {r.name: r for r in group.roles}
    treasurer = make_user(email='t@example.com', role='Treasurer')

    assert treasurer.can_grant(roles['Treasurer'])
    assert not treasurer.can_grant(roles['Chairperson'])
    assert not treasurer.can_grant(roles['Secretary'])   # edit_rules not held


def test_same_email_allowed_in_different_groups(make_group, make_user):
    other = make_group(name='Another Welfare', slug='another')
    make_user(email='sam@example.com')
    make_user(email='sam@example.com', group=other)

    assert User.query.filter_by(email='sam@example.com').count() == 2


def test_same_email_rejected_within_a_group(make_user):
    make_user(email='sam@example.com')
    with pytest.raises(IntegrityError):
        make_user(email='sam@example.com')
    db.session.rollback()


def test_email_taken_is_scoped_to_group(make_group, make_user):
    other = make_group(name='Another Welfare', slug='another')
    user = make_user(email='sam@example.com')

    assert User.email_taken('sam@example.com', user.group_id)
    assert not User.email_taken('sam@example.com', other.id)
    assert not User.email_taken('sam@example.com', None)
    assert not User.email_taken('sam@example.com', user.group_id, exclude_id=user.id)


@pytest.mark.parametrize('slug,valid', [
    ('mzugoss', True), ('class-of-2018', True),
    ('Mzugoss', False), ('-bad', False), ('a--b', False), ('', False), ('has space', False),
])
def test_slug_validation(slug, valid):
    assert Group.is_valid_slug(slug) is valid
