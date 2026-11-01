"""
Smoke tests: every url_for() target exists, and every parameterless GET
page renders without a server error for each kind of account. Catches
templates that reference removed endpoints or missing templates.
"""
import pathlib
import re

import pytest


_URL_FOR = re.compile(r"url_for\(\s*['\"]([\w.]+)['\"]")
_APP_DIR = pathlib.Path(__file__).resolve().parent.parent / 'app'


def test_every_url_for_target_exists(app):
    endpoints = set(app.view_functions) | {'static'}
    missing = [
        f'{path.relative_to(_APP_DIR)}:{n}: {endpoint}'
        for path in _APP_DIR.rglob('*') if path.suffix in ('.py', '.html', '.js')
        for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1)
        for endpoint in _URL_FOR.findall(line)
        if endpoint not in endpoints
    ]
    assert missing == []


@pytest.fixture
def accounts(make_user, make_superadmin):
    make_user(email='chair@example.com', role='Chairperson')
    make_user(email='treasurer@example.com', role='Treasurer')
    make_user(email='secretary@example.com', role='Secretary')
    make_superadmin(email='root@example.com')


@pytest.mark.parametrize('email,slug', [
    ('chair@example.com', 'mzugoss'),
    ('treasurer@example.com', 'mzugoss'),
    ('secretary@example.com', 'mzugoss'),
    ('root@example.com', None),
])
def test_pages_render_without_server_errors(app, client, login, accounts, email, slug):
    assert login(email, slug=slug).status_code == 302
    rules = [
        r.rule for r in app.url_map.iter_rules()
        if 'GET' in r.methods and not r.arguments and not r.rule.startswith('/static')
        and r.endpoint != 'auth.logout'
    ]

    errors = [(rule, client.get(rule).status_code) for rule in rules]
    assert [e for e in errors if e[1] >= 500] == []
