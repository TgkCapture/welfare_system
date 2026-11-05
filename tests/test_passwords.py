"""
Setting a new password for an officer who has forgotten theirs: by an
officer who manages them, by the platform, or from the command line.
"""
from werkzeug.security import check_password_hash

from app.models.audit import AuditEvent
from app.models.user import User

_NEW = {'new_password': 'brand-new-pass', 'confirm_password': 'brand-new-pass'}


def _password_events():
    return AuditEvent.query.filter_by(action='officer.password').all()


def test_chair_sets_a_new_password_for_a_treasurer(client, group, make_user, login):
    make_user(email='chair@example.com')
    treasurer = make_user(email='treasurer@example.com', role='Treasurer')
    login('chair@example.com')

    assert b'Set a new password' in client.get(f'/admin/users/{treasurer.id}/edit').data
    response = client.post(f'/admin/users/{treasurer.id}/password', data=_NEW)

    assert response.headers['Location'] == f'/admin/users/{treasurer.id}/edit'
    [event] = _password_events()
    assert (event.actor, event.group_id, event.details) == ('chair@example.com', group.id,
                                                            {'user_id': treasurer.id})

    client.get('/auth/logout')
    assert login('treasurer@example.com').headers['Location'] != '/'      # the old one fails
    assert login('treasurer@example.com', password='brand-new-pass').headers['Location'] == '/'


def test_passwords_must_match_and_be_long_enough(client, group, make_user, login):
    make_user(email='chair@example.com')
    treasurer = make_user(email='treasurer@example.com', role='Treasurer')
    login('chair@example.com')

    for data in ({'new_password': 'short', 'confirm_password': 'short'},
                 {'new_password': 'long-enough-1', 'confirm_password': 'long-enough-2'}):
        assert client.post(f'/admin/users/{treasurer.id}/password', data=data).status_code == 200
    assert check_password_hash(db_user(treasurer.id).password, 'secret123')
    assert _password_events() == []


def db_user(user_id):
    from app.extensions import db
    db.session.expire_all()
    return db.session.get(User, user_id)


def test_officers_without_manage_users_cannot_set_passwords(client, group, make_user, login):
    chair = make_user(email='chair@example.com')
    make_user(email='treasurer@example.com', role='Treasurer')
    login('treasurer@example.com')

    client.post(f'/admin/users/{chair.id}/password', data=_NEW)
    assert _password_events() == []
    assert check_password_hash(db_user(chair.id).password, 'secret123')


def test_own_password_goes_through_the_profile(client, group, make_user, login):
    chair = make_user(email='chair@example.com')
    login('chair@example.com')

    response = client.post(f'/admin/users/{chair.id}/password', data=_NEW)
    assert response.headers['Location'] == '/auth/profile'
    assert check_password_hash(db_user(chair.id).password, 'secret123')


def test_other_groups_officers_are_not_found(client, group, make_group, make_user, login):
    other = make_group(name='Another Welfare', slug='another')
    outsider = make_user(email='out@example.com', group=other)
    make_user(email='chair@example.com')
    login('chair@example.com')

    assert client.post(f'/admin/users/{outsider.id}/password', data=_NEW).status_code == 404


def test_platform_sets_a_locked_out_chairpersons_password(client, group, make_user, make_superadmin, login):
    chair = make_user(email='chair@example.com')
    make_superadmin()
    login('root@example.com', slug=None)

    page = client.get(f'/platform/groups/{group.id}').data
    assert f'/platform/groups/{group.id}/officers/{chair.id}/password'.encode() in page
    response = client.post(f'/platform/groups/{group.id}/officers/{chair.id}/password', data=_NEW)

    assert response.headers['Location'] == f'/platform/groups/{group.id}'
    assert check_password_hash(db_user(chair.id).password, 'brand-new-pass')
    [event] = _password_events()
    assert (event.actor, event.group_id) == ('root@example.com', group.id)


def test_platform_url_must_match_the_officers_group(client, group, make_group, make_user, make_superadmin, login):
    other = make_group(name='Another Welfare', slug='another')
    chair = make_user(email='chair@example.com')
    make_superadmin()
    login('root@example.com', slug=None)

    assert client.post(f'/platform/groups/{other.id}/officers/{chair.id}/password', data=_NEW).status_code == 404


def test_login_page_says_who_to_ask(client, group):
    assert b'Ask your chairperson' in client.get('/g/mzugoss/login').data


# ==================== COMMAND LINE ====================

def test_cli_lists_accounts_and_resets_a_password(app, group, make_user, make_superadmin):
    chair = make_user(email='chair@example.com')
    make_superadmin()
    cli = app.test_cli_runner()

    listing = cli.invoke(args=['list-users']).output
    assert 'platform' in listing and 'root@example.com' in listing
    assert 'mzugoss' in listing and 'chair@example.com' in listing and 'Chairperson' in listing

    result = cli.invoke(args=['reset-password', '--group', 'mzugoss', '--email', 'chair@example.com',
                              '--password', 'brand-new-pass'])
    assert 'New password set' in result.output
    assert check_password_hash(db_user(chair.id).password, 'brand-new-pass')
    [event] = _password_events()
    assert (event.actor, event.group_id) == ('command line', group.id)


def test_cli_resets_a_superadmin_and_rejects_unknown_accounts(app, group, make_superadmin):
    root = make_superadmin()
    cli = app.test_cli_runner()

    assert 'No such account' in cli.invoke(args=['reset-password', '--group', 'mzugoss',
                                                 '--email', 'root@example.com', '--password', 'brand-new-pass']).output
    assert 'at least 8' in cli.invoke(args=['reset-password', '--email', 'root@example.com',
                                            '--password', 'short']).output
    assert 'New password set' in cli.invoke(args=['reset-password', '--email', 'root@example.com',
                                                  '--password', 'brand-new-pass']).output
    assert check_password_hash(db_user(root.id).password, 'brand-new-pass')
