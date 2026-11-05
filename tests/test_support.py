"""
Platform support sessions: a superadmin looks at a group's screens,
read-only, for a limited time, with the reason and every page logged
for the group.
"""
from datetime import datetime, timedelta

import pandas as pd
import pytest

from app.extensions import db
from app.models.audit import AuditEvent
from app.models.member import Member
from app.services.period_store import PeriodStore


def _actions(group):
    return [e.action for e in AuditEvent.for_group(group.id).order_by(AuditEvent.id)]


@pytest.fixture
def root(client, group, make_superadmin, login):
    make_superadmin()
    login('root@example.com', slug=None)


def _start(client, group, reason='Treasurer says March total is wrong'):
    return client.post(f'/platform/groups/{group.id}/support', data={'reason': reason})


def test_without_a_session_a_superadmin_sees_no_group_screens(client, group, root):
    assert client.get('/').headers['Location'] == '/platform/'
    assert client.get('/members').status_code != 200


def test_a_session_needs_a_reason(client, group, root):
    _start(client, group, reason='')
    assert client.get('/').headers['Location'] == '/platform/'
    assert 'support.start' not in _actions(group)


def test_a_session_shows_the_group_and_logs_what_was_opened(client, group, root):
    PeriodStore.sync(group, {'data': pd.DataFrame([('Ann', 1000)], columns=['Name', 'March']),
                             'name_col': 'Name', 'month_col': 'March', 'year': 2026, 'month': 'March'})

    assert _start(client, group).headers['Location'] == '/'
    page = client.get('/members')

    assert page.status_code == 200 and b'Ann' in page.data
    assert b'Support session' in page.data
    start, view = AuditEvent.for_group(group.id).filter(AuditEvent.action.like('support.%')) \
        .order_by(AuditEvent.id).all()[:2]
    assert start.summary.endswith('Treasurer says March total is wrong') and start.in_support
    assert (view.action, view.summary, view.in_support) == ('support.view', 'Viewed /members', True)


def test_a_session_is_read_only(client, group, root):
    PeriodStore.sync(group, {'data': pd.DataFrame([('Ann', 1000)], columns=['Name', 'March']),
                             'name_col': 'Name', 'month_col': 'March', 'year': 2026, 'month': 'March'})
    ann = Member.for_group(group.id).one()
    _start(client, group)

    client.post(f'/members/{ann.id}/rename', data={'name': 'Changed'})
    client.post('/settings/public', data={'action': 'toggle_code'})

    assert db.session.get(Member, ann.id).display_name == 'Ann'
    assert group.settings.access_code_enabled is True
    assert 'member.rename' not in _actions(group)


def test_looking_does_not_tick_setup_steps(client, group, root):
    _start(client, group)
    client.get('/settings/public')
    assert 'public' not in (group.settings.setup_marks or [])


def test_ending_and_logging_out_close_the_session(client, group, root, login):
    _start(client, group)
    client.post('/platform/support/end')
    assert client.get('/').headers['Location'] == '/platform/'

    _start(client, group)
    client.get('/auth/logout')
    assert _actions(group).count('support.end') == 2


def test_a_session_runs_out(client, group, root, app):
    _start(client, group)
    with client.session_transaction() as session:
        session['support']['started'] = (datetime.utcnow() - timedelta(minutes=61)).isoformat()
        session.modified = True

    assert client.get('/members').headers['Location'] == '/platform/'
    end = AuditEvent.for_group(group.id).filter_by(action='support.end').one()
    assert end.summary == 'Platform support session ran out'


def test_platform_actions_during_a_session_are_not_marked_as_support(client, group, make_group, root):
    other = make_group(name='Another Welfare', slug='another')
    _start(client, group)

    client.post(f'/platform/groups/{other.id}/toggle')

    event = AuditEvent.query.filter_by(action='group.toggle').one()
    assert (event.group_id, event.in_support) == (other.id, False)


def test_the_group_sees_the_session_in_its_audit_log(client, group, make_superadmin, make_user, login):
    make_superadmin()
    make_user(email='chair@example.com')
    login('root@example.com', slug=None)
    _start(client, group)
    client.get('/members')
    client.get('/auth/logout')

    login('chair@example.com')
    page = client.get('/audit?area=support').data
    assert b'Treasurer says March total is wrong' in page and b'Viewed /members' in page
