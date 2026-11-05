"""
The setup checklist: steps tick themselves from the group's data (or when
an officer saves or views a page), it shows on the dashboard until it is
done or hidden, and existing groups start with it hidden.
"""
import pandas as pd
import pytest

from app.extensions import db
from app.models.group import Group
from app.models.ledger import PayoutPurpose
from app.models.rules import RuleSection
from app.services import setup
from app.services.period_store import PeriodStore


def _done(group):
    return {s.key for s in setup.steps(group) if s.done}


@pytest.fixture
def chair(client, make_user, login):
    make_user(email='chair@example.com')
    login('chair@example.com')


def test_a_new_group_starts_with_nothing_done(app, group):
    assert _done(group) == set()
    assert setup.progress(group)['next'].key == 'branding'


def test_steps_tick_themselves_from_the_data(app, group, make_user):
    db.session.add(PayoutPurpose(group_id=group.id, name='Funeral condolence'))
    db.session.add(RuleSection(group_id=group.id, title='Rules', body='Pay monthly.'))
    group.settings.google_sheet_url = 'https://docs.google.com/spreadsheets/d/x'
    db.session.commit()
    make_user(email='one@example.com')
    make_user(email='two@example.com', role='Treasurer')
    PeriodStore.sync(group, {'data': pd.DataFrame([('Ann', 1000)], columns=['Name', 'March']),
                             'name_col': 'Name', 'month_col': 'March', 'year': 2026, 'month': 'March'})

    assert _done(group) == {'purposes', 'workbook', 'sync', 'rules', 'officers'}


def test_branding_and_public_page_tick_when_an_officer_does_them(client, group, chair):
    client.post('/settings', data={'section': 'branding', 'display_name': 'Mzugoss', 'short_name': '',
                                   'currency': 'MWK', 'primary_color': '#1d4ed8', 'report_title': ''})
    client.get('/settings/public')
    assert {'branding', 'public'} <= _done(db.session.get(Group, group.id))


def test_dashboard_shows_the_checklist_until_hidden(client, group, chair):
    page = client.get('/').data.decode()
    assert 'Set up your group: 0 of 7 done' in page
    assert "Next: Check your group&#39;s name and colour" in page

    client.post('/setup/toggle', data={'action': 'hide'})
    assert 'Set up your group' not in client.get('/').data.decode()
    assert db.session.get(Group, group.id).settings.setup_dismissed

    client.post('/setup/toggle', data={'action': 'show'})
    assert 'Set up your group' in client.get('/').data.decode()


def test_finished_setup_leaves_the_dashboard(client, group, chair, monkeypatch):
    monkeypatch.setattr(setup, 'progress', lambda g: {'steps': [], 'done': 7, 'total': 7,
                                                      'complete': True, 'next': None})
    assert 'Set up your group' not in client.get('/').data.decode()


def test_checklist_page_shows_each_step_and_who_can_do_it(client, group, make_user, login):
    make_user(email='sec@example.com', role='Secretary')        # can edit rules only
    login('sec@example.com')
    page = client.get('/setup').data.decode()

    assert '0 of 7 steps done' in page
    assert page.count('Ask an officer whose role allows this.') == 6     # all but the rules step
    assert '/settings/rules' in page
    assert client.post('/setup/toggle', data={'action': 'hide'}).status_code == 403


def test_platform_created_groups_get_the_checklist(client, make_superadmin, login):
    make_superadmin()
    login('root@example.com', slug=None)
    client.post('/platform/groups/new', data={
        'name': 'New Welfare', 'slug': 'new-welfare', 'officer_email': 'c@new.example',
        'officer_password': 'longenough', 'confirm_password': 'longenough'})
    group = Group.query.filter_by(slug='new-welfare').one()
    assert setup.show_on_dashboard(group)
