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


def test_legacy_roles_map_to_presets(group):
    assert Role.for_legacy_role(group.id, 'admin').name == 'Chairperson'
    assert Role.for_legacy_role(group.id, 'clerk').name == 'Treasurer'
    assert Role.for_legacy_role(group.id, 'viewer') is None
    assert Role.for_legacy_role(None, 'admin') is None


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
