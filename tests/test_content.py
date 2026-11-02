"""
Group-configurable content: welfare rules written by each group's officers,
and each group's branding wherever the app shows a name, title or currency.
"""
import ast
import pathlib
import re

import pandas as pd
import pytest

from app.extensions import db
from app.models.group import Group
from app.models.rules import RuleSection
from app.services.period_store import PeriodStore
from app.services.rules_markup import parse

APP_DIR = pathlib.Path(__file__).resolve().parent.parent / 'app'


def _section(group, title, body='', position=0, subtitle=None):
    section = RuleSection(group_id=group.id, title=title, body=body, position=position, subtitle=subtitle)
    db.session.add(section)
    db.session.commit()
    return section


# ==================== NO HARD-CODED GROUP ====================

def test_no_group_name_is_hard_coded():
    """Group names come from the group's settings, never from the code.

    Templates, scripts and styles are checked in full; Python files are
    checked in their string literals (comments and docstrings may still
    mention the original layout).
    """
    pattern = re.compile(r'mzugoss|class of 2018', re.I)
    found = []
    for path in list((APP_DIR / 'templates').rglob('*.html')) + list((APP_DIR / 'static').rglob('*.[jc]s*')):
        for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            if pattern.search(line) and 'e.g. mzugoss' not in line:     # example slug in a placeholder
                found.append(f'{path.relative_to(APP_DIR)}:{n}')
    for path in APP_DIR.rglob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                      if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef))
                      and node.body and isinstance(node.body[0], ast.Expr)
                      and isinstance(node.body[0].value, ast.Constant)}
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings
                    and pattern.search(node.value) and 'e.g. mzugoss' not in node.value):
                found.append(f'{path.relative_to(APP_DIR)}:{node.lineno}')
    assert found == []


# ==================== RULES MARKUP ====================

def test_markup_blocks():
    blocks = parse('Intro line\nruns on.\n\n- Mother\n- Father\n\n1. First\n2. Second\n\n> Note here')
    assert [(b.kind, [str(i) for i in b.items]) for b in blocks] == [
        ('p', ['Intro line runs on.']),
        ('ul', ['Mother', 'Father']),
        ('ol', ['First', 'Second']),
        ('note', ['Note here']),
    ]


def test_markup_bold_italic_and_mixed_lines():
    blocks = parse('Released only for **immediate family**:\n- *Mother*\n- Father_s_ house')
    assert str(blocks[0].items[0]) == 'Released only for <b>immediate family</b>:'
    assert [str(i) for i in blocks[1].items] == ['<i>Mother</i>', 'Father_s_ house']


def test_markup_escapes_html():
    html = str(parse('<script>alert(1)</script> **<b>x</b>** & "q"')[0].items[0])
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert html.count('<b>') == 1 and '&amp;' in html


# ==================== RULES PAGES ====================

@pytest.fixture
def two_groups(group, make_group):
    other = make_group(name='Another Welfare', slug='another')
    _section(group, 'Funeral support', '**Amount:** K50,000', subtitle='When someone dies')
    _section(other, 'Their rule', 'Theirs only')
    return group, other


def test_officers_see_their_own_groups_rules(client, two_groups, make_user, login):
    make_user(email='t@example.com', role='Treasurer')
    login('t@example.com')

    page = client.get('/welfare-rules').data
    assert b'Funeral support' in page and b'<b>Amount:</b> K50,000' in page
    assert b'Their rule' not in page
    assert b'Edit rules' not in page                  # Treasurer can't edit rules


def test_public_rules_page_and_pdf(client, two_groups):
    page = client.get('/g/another/rules')
    assert b'Their rule' in page.data and b'Funeral support' not in page.data
    assert b'Another Welfare' in page.data and page.headers['X-Robots-Tag'] == 'noindex'

    pdf = client.get('/g/another/rules.pdf')
    assert pdf.data.startswith(b'%PDF') and 'another_welfare_rules.pdf' in pdf.headers['Content-Disposition']
    assert client.get('/g/nope/rules').status_code == 404


def test_rules_pdf_for_an_officer(client, two_groups, make_user, login):
    make_user()
    login()
    response = client.get('/welfare-rules/download')
    assert response.data.startswith(b'%PDF')
    assert 'mzugoss_welfare_rules.pdf' in response.headers['Content-Disposition']


def test_old_rules_links_send_visitors_to_a_group(client, group, make_group):
    assert client.get('/welfare-rules').headers['Location'] == '/g/mzugoss/rules'      # the only group
    make_group(name='Another Welfare', slug='another')
    assert client.get('/welfare-rules').headers['Location'] == '/auth/login'           # which one?
    client.set_cookie('last_group', 'another')
    assert client.get('/welfare-rules').headers['Location'] == '/g/another/rules'
    assert client.get('/welfare-rules/download').headers['Location'] == '/g/another/rules.pdf'


def test_a_group_without_rules_says_so(client, group):
    assert b'No rules written yet' in client.get('/g/mzugoss/rules').data


# ==================== RULES EDITOR ====================

@pytest.fixture
def secretary(client, make_user, login):
    make_user(email='sec@example.com', role='Secretary')     # has edit_rules
    login('sec@example.com')


def test_add_edit_move_and_delete_sections(client, group, secretary):
    client.post('/settings/rules', data={'title': 'First', 'subtitle': ''})
    response = client.post('/settings/rules', data={'title': 'Second'})
    second = RuleSection.for_group(group.id).filter_by(title='Second').one()
    assert response.headers['Location'] == f'/settings/rules/{second.id}'

    client.post(f'/settings/rules/{second.id}', data={'title': 'Second', 'subtitle': 'Sub', 'body': '- a\n- b'})
    assert db.session.get(RuleSection, second.id).body == '- a\n- b'
    assert b'<li>a</li>' in client.get(f'/settings/rules/{second.id}').data

    client.post(f'/settings/rules/{second.id}/move', data={'direction': 'up'})
    assert [s.title for s in RuleSection.ordered(group.id)] == ['Second', 'First']

    client.post(f'/settings/rules/{second.id}/delete')
    assert [s.title for s in RuleSection.ordered(group.id)] == ['First']


def test_a_section_needs_a_title(client, group, secretary):
    client.post('/settings/rules', data={'title': '   '})
    assert RuleSection.for_group(group.id).count() == 0


def test_rules_editor_needs_edit_rules_and_is_scoped(client, two_groups, make_user, login):
    _, other = two_groups
    theirs = RuleSection.for_group(other.id).one()
    make_user(email='t@example.com', role='Treasurer')
    login('t@example.com')
    assert client.get('/settings/rules').status_code != 200

    client.get('/auth/logout')
    make_user(email='sec@example.com', role='Secretary')
    login('sec@example.com')
    assert client.post(f'/settings/rules/{theirs.id}', data={'title': 'Hijacked'}).status_code == 404
    assert client.post(f'/settings/rules/{theirs.id}/delete').status_code == 404
    assert db.session.get(RuleSection, theirs.id).title == 'Their rule'


# ==================== BRANDING ====================

@pytest.fixture
def chair(client, make_user, login):
    make_user(email='chair@example.com')
    login('chair@example.com')


BRANDING = {'section': 'branding', 'display_name': 'Mzuzu Old Students', 'short_name': 'MOS',
            'currency': 'zmw', 'primary_color': '#AA3300', 'report_title': 'MOS monthly report'}


def test_branding_shows_on_pages(client, group, chair):
    client.post('/settings', data=BRANDING)

    settings = db.session.get(Group, group.id).settings
    assert (settings.display_name, settings.currency, settings.primary_color) == (
        'Mzuzu Old Students', 'ZMW', '#aa3300')
    page = client.get('/settings').data.decode()
    assert '<title>Settings — Mzuzu Old Students</title>' in page
    assert 'topnav__logo-primary">MOS<' in page
    assert '--clr-primary: #aa3300' in page


@pytest.mark.parametrize('field,value', [
    ('display_name', ''), ('currency', 'KWACHA'), ('primary_color', 'red'), ('short_name', 'x' * 31),
])
def test_invalid_branding_is_rejected(client, group, chair, field, value):
    client.post('/settings', data={**BRANDING, field: value})
    assert db.session.get(Group, group.id).settings.display_name != 'Mzuzu Old Students'


def test_reports_carry_the_groups_brand(app, group):
    group.settings.currency, group.settings.report_title = 'ZMW', 'Our report'
    db.session.commit()
    PeriodStore.sync(group, {'data': pd.DataFrame([('Ann', 100)], columns=['Name', 'March']),
                             'name_col': 'Name', 'month_col': 'March', 'year': 2026, 'month': 'March'})

    data = PeriodStore.report_data(group.id, 2026, 3)

    assert (data['currency'], data['report_title'], data['group_name']) == ('ZMW', 'Our report',
                                                                            'Mzugoss Class of 2018')


def test_platform_pages_use_the_platform_name(client, make_superadmin, login):
    make_superadmin()
    login('root@example.com', slug=None)
    assert b'<title>Platform \xe2\x80\x94 Welfare System</title>' in client.get('/platform/').data


def test_public_pages_use_the_viewed_groups_brand(client, group, make_group):
    other = make_group(name='Another Welfare', slug='another')
    other.settings.primary_color = '#008800'
    db.session.commit()
    page = client.get('/g/another/login').data.decode()
    assert 'Another Welfare' in page and 'Mzugoss' not in page
