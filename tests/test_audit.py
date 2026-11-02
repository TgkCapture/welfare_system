"""
The audit log: changes, sign-ins and platform actions are recorded with who
did them; officers with manage_users read their own group's log only.
"""
import pandas as pd
import pytest

from app.extensions import db
from app.models.audit import AuditEvent
from app.models.member import Member, normalise_name
from app.models.rules import RuleSection
from app.models.user import User
from app.services import audit
from app.services.period_store import PeriodStore


def _sync(group, rows, month='March', year=2026):
    PeriodStore.sync(group, {'data': pd.DataFrame(rows, columns=['Name', month]), 'name_col': 'Name',
                             'month_col': month, 'year': year, 'month': month})


def _events(action=None):
    query = AuditEvent.query.order_by(AuditEvent.id)
    if action:
        query = query.filter_by(action=action)
    return query.all()


@pytest.fixture
def chair(client, group, make_user, login):
    user = make_user(email='chair@example.com')
    login('chair@example.com')
    return user


# ==================== WHAT IS RECORDED ====================

def test_a_change_is_recorded_with_who_and_where(client, group, chair):
    _sync(group, [('Ann Banda', 1000)])
    ann = Member.for_group(group.id).filter_by(normalised_name=normalise_name('Ann Banda')).one()

    client.post(f'/members/{ann.id}/rename', data={'name': 'Ann B. Banda'})

    event = _events('member.rename')[0]
    assert event.summary == 'Renamed the member Ann Banda to Ann B. Banda'
    assert (event.group_id, event.user_id, event.actor) == (group.id, chair.id, 'chair@example.com')
    assert event.ip_address == '127.0.0.1' and event.in_support is False
    assert event.details == {'member_id': ann.id}


def test_sign_ins_are_recorded_in_the_group(client, group, make_user, login):
    make_user(email='chair@example.com')

    login('chair@example.com', password='wrong-password')
    login('nobody@example.com')
    login('chair@example.com')

    failed, ok = _events('auth.failed'), _events('auth.login')
    assert [e.actor for e in failed] == ['chair@example.com', 'nobody@example.com']
    assert all(e.group_id == group.id for e in failed + ok)
    assert failed[1].user_id is None
    assert ok[0].summary == 'chair@example.com signed in'


def test_secrets_are_never_written_to_the_log(client, group, chair):
    _sync(group, [('Ann', 1000)])
    ann = Member.for_group(group.id).one()
    client.post('/settings/public', data={'action': 'set_code', 'code': 'SECRET42'})
    pin_page = client.post(f'/members/{ann.id}/pin').data.decode()
    client.post('/auth/change-password', data={'current_password': 'secret123', 'new_password': 'n3w-password',
                                               'confirm_password': 'n3w-password'})

    import re
    pin = re.search(r'<code[^>]*>(\d{6})</code>', pin_page).group(1)
    logged = ' '.join(f'{e.summary} {e.details}' for e in _events())
    assert 'SECRET42' not in logged and pin not in logged and 'n3w-password' not in logged
    assert {'settings.access_code', 'member.pin', 'auth.password'} <= {e.action for e in _events()}


def test_rule_edits_keep_the_previous_wording(client, group, chair):
    section = RuleSection(group_id=group.id, position=1, title='Funerals', body='Old wording')
    db.session.add(section)
    db.session.commit()

    client.post(f'/settings/rules/{section.id}', data={'title': 'Funerals', 'body': 'New wording'})
    client.post(f'/settings/rules/{section.id}/delete')

    edit, delete = _events('rules.edit')[0], _events('rules.delete')[0]
    assert edit.details['before']['body'] == 'Old wording'
    assert delete.details['before']['body'] == 'New wording'


def test_officer_changes_name_what_changed(client, group, chair, make_user):
    clerk = make_user(email='clerk@example.com', role='Secretary')
    treasurer_role = [r for r in group.roles if r.name == 'Treasurer'][0]

    client.post(f'/admin/users/{clerk.id}/edit', data={'email': 'clerk@example.com', 'role': treasurer_role.id,
                                                       'is_active': 'y'})
    client.post(f'/admin/users/{clerk.id}/delete')

    edit = _events('officer.edit')[0]
    assert edit.details['changes'] == {'role': ['Secretary', 'Treasurer']}
    assert _events('officer.delete')[0].summary == 'Deleted the officer clerk@example.com'


def test_an_entry_outlives_the_officer_who_made_it(client, group, make_user, login):
    make_user(email='chair@example.com')
    leaver_id = make_user(email='leaver@example.com').id
    login('leaver@example.com')

    client.post('/auth/delete-account', data={'confirm_text': 'DELETE'})

    entries = AuditEvent.query.filter_by(actor='leaver@example.com').all()
    assert {e.action for e in entries} == {'auth.login', 'officer.delete'}
    assert db.session.get(User, leaver_id) is None
    assert all(e.user_id in (leaver_id, None) for e in entries)


# ==================== READING THE LOG ====================

def test_audit_page_shows_only_the_groups_own_entries(client, group, make_group, chair):
    other = make_group(name='Another Welfare', slug='another')
    audit.record('settings.branding', 'Changed the branding in another group', group_id=other.id,
                 actor='them@example.com')
    audit.record('settings.branding', 'Changed our branding', group_id=group.id, actor='chair@example.com')

    page = client.get('/audit').data
    assert b'Changed our branding' in page and b'another group' not in page

    filtered = client.get('/audit?area=member').data
    assert b'Changed our branding' not in filtered


def test_audit_page_needs_manage_users(client, group, make_user, login):
    make_user(email='t@example.com', role='Treasurer')
    login('t@example.com')
    assert client.get('/audit').status_code != 200


def test_activity_page_shows_your_own_entries(client, group, chair, make_user):
    audit.record('member.rename', 'Someone else renamed a member', group_id=group.id,
                 user_id=make_user(email='x@example.com').id, actor='x@example.com')

    page = client.get('/auth/activity-log').data
    assert b'chair@example.com signed in' in page and b'Someone else' not in page


def test_platform_actions_are_recorded_against_the_group(client, group, make_superadmin, login):
    make_superadmin()
    login('root@example.com', slug=None)

    client.post(f'/platform/groups/{group.id}/toggle')

    event = _events('group.toggle')[0]
    assert (event.group_id, event.summary) == (group.id, 'Platform suspended the group')
    assert b'Platform suspended the group' in client.get(f'/platform/audit?group={group.id}').data


def test_platform_audit_page_is_for_superadmins(client, group, chair):
    assert client.get('/platform/audit').status_code != 200


# ==================== POSTGRES READINESS ====================

def test_database_url_uses_the_psycopg_driver(monkeypatch):
    from app.config import database_url

    for given in ('postgres://u:p@h/db', 'postgresql://u:p@h/db'):
        monkeypatch.setenv('DATABASE_URL', given)
        assert database_url() == 'postgresql+psycopg://u:p@h/db'
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///x.db')
    assert database_url() == 'sqlite:///x.db'


def test_migrations_give_booleans_boolean_defaults():
    """Postgres refuses DEFAULT 0 on a boolean column; use sa.true()/sa.false()."""
    import pathlib
    import re

    for path in pathlib.Path('migrations/versions').glob('*.py'):
        for line in path.read_text(encoding='utf-8').splitlines():
            if 'sa.Boolean()' in line and 'server_default' in line:
                assert re.search(r'server_default=sa\.(true|false)\(\)', line), f'{path.name}: {line.strip()}'


def test_an_officer_with_reports_and_syncs_can_be_deleted(client, group, chair, make_user):
    """Their reports, syncs and access records stay; only the link to the account goes."""
    from app.models.ledger import SyncRun
    from app.models.report import GeneratedReport, ReportAccessLog

    clerk_id = make_user(email='clerk@example.com', role='Treasurer').id
    report = GeneratedReport(group_id=group.id, month=3, year=2026, report_type='contributions',
                             filename='r.pdf', file_path='/nowhere/r.pdf', generated_by=clerk_id)
    db.session.add(report)
    db.session.flush()
    db.session.add(ReportAccessLog(group_id=group.id, report_id=report.id, user_id=clerk_id, action='generate'))
    db.session.add(SyncRun(group_id=group.id, synced_by=clerk_id, details={}, warnings=[]))
    db.session.commit()
    report_id = report.id

    client.post(f'/admin/users/{clerk_id}/delete')

    assert db.session.get(User, clerk_id) is None
    report = db.session.get(GeneratedReport, report_id)
    assert report is not None and report.generated_by is None
    assert ReportAccessLog.query.one().user_id is None
    assert SyncRun.query.one().synced_by is None
