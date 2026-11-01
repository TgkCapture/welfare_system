"""
Tenant isolation.

  - A static guard: controllers and services may only query group-owned
    tables through ``for_group()`` / ``get_for_group_or_404()``. A raw query
    must carry a marker comment saying why it is safe.
  - A cross-tenant crawl: an officer of one group tries every route that
    takes an id, using another group's ids, and must get nothing.
  - The freshly generated report kept in the session never reaches
    another officer.
"""
import pathlib
import re

import pytest

from app.extensions import db
from app.models.report import GeneratedReport
from app.models.role import Role
from app.models.user import User

_APP_DIR = pathlib.Path(__file__).resolve().parent.parent / 'app'
_TENANT_MODELS = r'(?:User|Role|GeneratedReport|ReportAccessLog)'
_RAW_QUERY = re.compile(
    rf'\b{_TENANT_MODELS}\.query\b'
    rf'|db\.session\.get\(\s*{_TENANT_MODELS}\b'
    r'|db\.session\.query\('
    r'|\.get_or_404\('
)
# A raw query is allowed only with one of these markers on the same line
_MARKERS = ('# platform-wide', '# own account')


def test_group_owned_tables_are_only_queried_through_tenant_helpers():
    offenders = [
        f'{path.relative_to(_APP_DIR)}:{n}: {line.strip()}'
        for folder in ('controllers', 'services')
        for path in (_APP_DIR / folder).rglob('*.py')
        for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1)
        if _RAW_QUERY.search(line) and not any(m in line for m in _MARKERS)
    ]
    assert offenders == []


# ==================== CROSS-TENANT CRAWL ====================

@pytest.fixture
def other_group_data(make_group, make_user, tmp_path):
    """A second group with an officer and a report whose file exists."""
    other = make_group(name='Another Welfare', slug='another')
    officer = make_user(email='out@example.com', group=other, role='Treasurer')
    pdf = tmp_path / 'theirs.pdf'
    pdf.write_bytes(b'%PDF-1.4 theirs')
    report = GeneratedReport(
        group_id=other.id, month=3, year=2026, filename='theirs.pdf',
        file_path=str(pdf), generated_by=officer.id, total_contributions=999,
    )
    db.session.add(report)
    db.session.commit()
    return {
        'report_id': report.id,
        'user_id':   officer.id,
        'role_id':   Role.for_group(other.id).first().id,
    }


def test_officer_cannot_reach_another_groups_records(app, client, make_user, login, other_group_data):
    make_user(email='chair@example.com', role='Chairperson')   # every permission
    login('chair@example.com')

    tried = []
    for rule in app.url_map.iter_rules():
        args = rule.arguments
        if not args or not args <= set(other_group_data):
            continue
        url = rule.build({a: other_group_data[a] for a in args})[1]
        for method in sorted(rule.methods & {'GET', 'POST'}):
            response = client.open(url, method=method)
            tried.append((method, url, response.status_code))
            assert response.status_code != 200, (method, url)
            assert b'theirs' not in response.data, (method, url)

    assert len(tried) >= 10   # the crawl actually exercised the id routes

    report = db.session.get(GeneratedReport, other_group_data['report_id'])
    officer = db.session.get(User, other_group_data['user_id'])
    assert report is not None and not report.is_archived
    assert officer is not None and officer.is_active


# ==================== SESSION REPORT ====================

def _upload(client, workbook):
    with open(workbook, 'rb') as fh:
        return client.post(
            '/upload',
            data={'file': (fh, 'mzugoss.xlsx'), 'year': '2026', 'month': '3'},
            content_type='multipart/form-data',
        )


_SESSION_REPORT_PAGES = (
    '/reports/preview', '/reports/download',
    '/reports/paid-members', '/reports/paid-members/download',
)


def test_session_report_is_cleared_on_logout(client, make_group, make_user, login, mzugoss_workbook):
    other = make_group(name='Another Welfare', slug='another')
    make_user(email='chair@example.com')
    make_user(email='out@example.com', group=other)

    login('chair@example.com')
    assert _upload(client, mzugoss_workbook).status_code == 302
    assert client.get('/reports/preview').status_code == 200

    client.get('/auth/logout')
    login('out@example.com', slug='another')

    for page in _SESSION_REPORT_PAGES:
        response = client.get(page)
        assert response.status_code == 302, page
        assert b'Alinafe' not in response.data, page


def test_session_report_belongs_to_the_officer_who_generated_it(client, make_user, login, mzugoss_workbook):
    make_user(email='chair@example.com')
    other = make_user(email='treasurer@example.com', role='Treasurer')
    login('chair@example.com')
    _upload(client, mzugoss_workbook)

    # Simulate a session that survived without a logout (e.g. a stale cookie)
    with client.session_transaction() as sess:
        sess['_user_id'] = str(other.id)

    for page in _SESSION_REPORT_PAGES:
        assert client.get(page).status_code == 302, page
