import pytest
from werkzeug.security import check_password_hash

from app.models.group import Group
from app.models.user import User


@pytest.fixture
def cli(app):
    return app.test_cli_runner()


def test_create_group_seeds_settings_and_roles(cli):
    result = cli.invoke(args=['create-group', '--name', 'Mzugoss Class of 2018', '--slug', 'mzugoss'])

    assert '✓' in result.output
    group = Group.query.filter_by(slug='mzugoss').one()
    assert group.settings.display_name == 'Mzugoss Class of 2018'
    assert group.settings.currency == 'MWK'
    assert {r.name for r in group.roles} == {'Chairperson', 'Treasurer', 'Secretary'}


@pytest.mark.parametrize('slug', ['Bad Slug', 'mzugoss'])
def test_create_group_rejects_invalid_or_duplicate_slug(cli, group, slug):
    result = cli.invoke(args=['create-group', '--name', 'X', '--slug', slug])
    assert '✗' in result.output
    assert Group.query.count() == 1


def test_create_admin_creates_chairperson_in_group(cli, group):
    result = cli.invoke(args=[
        'create-admin', '--group', 'mzugoss',
        '--email', 'chair@example.com', '--password', 'longenough',
    ])

    assert '✓' in result.output
    user = User.query.filter_by(email='chair@example.com').one()
    assert user.group_id == group.id
    assert user.role.name == 'Chairperson'
    assert not user.is_superadmin
    assert check_password_hash(user.password, 'longenough')


def test_create_admin_requires_existing_group(cli):
    result = cli.invoke(args=[
        'create-admin', '--group', 'nope', '--email', 'a@example.com', '--password', 'longenough',
    ])
    assert 'create-group' in result.output
    assert User.query.count() == 0


def test_create_superadmin_has_no_group(cli):
    result = cli.invoke(args=[
        'create-superadmin', '--email', 'root@example.com', '--password', 'longenough',
    ])

    assert '✓' in result.output
    user = User.query.filter_by(email='root@example.com').one()
    assert user.is_superadmin
    assert user.group_id is None
    assert user.role is None


def test_create_superadmin_rejects_short_password(cli):
    result = cli.invoke(args=[
        'create-superadmin', '--email', 'root@example.com', '--password', 'short',
    ])
    assert '8 characters' in result.output
    assert User.query.count() == 0


def test_create_superadmin_rejects_duplicate_superadmin_email(cli, make_superadmin):
    make_superadmin(email='root@example.com')
    result = cli.invoke(args=[
        'create-superadmin', '--email', 'root@example.com', '--password', 'longenough',
    ])
    assert 'already registered' in result.output
    assert User.query.filter_by(is_superadmin=True).count() == 1


def test_superadmin_may_share_email_with_an_officer(cli, make_user):
    # Separate logins (/platform vs /g/<slug>) keep the two accounts apart
    make_user(email='sam@example.com')
    result = cli.invoke(args=[
        'create-superadmin', '--email', 'sam@example.com', '--password', 'longenough',
    ])
    assert '✓' in result.output
