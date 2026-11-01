"""
Runs the real Alembic migrations against a file database seeded the way
an existing single-group Mzugoss install looks before step 1a.
"""
import json
import os

import pytest
import sqlalchemy as sa
from flask_migrate import upgrade

from app import create_app

MIGRATIONS = os.path.join(os.path.dirname(__file__), '..', 'migrations')
BASELINE = '365dc0d4aa41'


@pytest.fixture
def migrated_legacy_db(tmp_path):
    app = create_app('testing', {
        'SQLALCHEMY_DATABASE_URI': f"sqlite:///{tmp_path / 'legacy.db'}",
        'UPLOAD_FOLDER': str(tmp_path / 'uploads'),
        'REPORT_FOLDER': str(tmp_path / 'reports'),
        'LOGS_FOLDER':   str(tmp_path / 'logs'),
    })
    with app.app_context():
        from app.extensions import db

        upgrade(directory=MIGRATIONS, revision=BASELINE)
        with db.engine.begin() as conn:
            conn.execute(sa.text(
                "INSERT INTO users (id, email, password, role, is_active) VALUES "
                "(1, 'admin@mzugoss.com', 'x', 'admin', 1),"
                "(2, 'clerk@mzugoss.com', 'x', 'clerk', 1),"
                "(3, 'viewer@mzugoss.com', 'x', 'viewer', 1)"
            ))
            conn.execute(sa.text(
                "INSERT INTO generated_reports (id, month, year, report_type, filename, "
                "file_path, generated_by, generated_at, is_archived) VALUES "
                "(1, 3, 2026, 'contributions', 'r.pdf', '/r.pdf', 1, '2026-03-31', 0)"
            ))
            conn.execute(sa.text(
                "INSERT INTO report_access_logs (report_id, user_id, accessed_at, action) "
                "VALUES (1, 1, '2026-03-31', 'generate')"
            ))
            conn.execute(sa.text(
                "INSERT INTO settings (key, value) VALUES "
                "('google_sheets_url', 'https://docs.google.com/spreadsheets/d/abc'),"
                "('report_retention_days', '14')"
            ))

        upgrade(directory=MIGRATIONS)

        with db.engine.connect() as conn:
            yield conn


def _rows(conn, sql):
    return [tuple(r) for r in conn.execute(sa.text(sql))]


def test_creates_mzugoss_group_with_copied_settings(migrated_legacy_db):
    conn = migrated_legacy_db
    assert _rows(conn, 'SELECT name, slug FROM groups') == [('Mzugoss Class of 2018', 'mzugoss')]
    assert _rows(conn, 'SELECT google_sheet_url, report_retention_days, currency FROM group_settings') == [
        ('https://docs.google.com/spreadsheets/d/abc', 14, 'MWK'),
    ]


def test_seeds_preset_roles(migrated_legacy_db):
    roles = {name: json.loads(perms) for name, perms in
             _rows(migrated_legacy_db, 'SELECT name, permissions FROM roles')}
    assert set(roles) == {'Chairperson', 'Treasurer', 'Secretary'}
    assert 'manage_users' in roles['Chairperson']
    assert 'manage_users' not in roles['Treasurer']


def test_maps_users_to_group_roles_and_deactivates_viewers(migrated_legacy_db):
    users = _rows(migrated_legacy_db, """
        SELECT u.email, r.name, u.group_id IS NOT NULL, u.is_active, u.is_superadmin
        FROM users u LEFT JOIN roles r ON r.id = u.role_id ORDER BY u.id
    """)
    assert users == [
        ('admin@mzugoss.com',  'Chairperson', 1, 1, 0),
        ('clerk@mzugoss.com',  'Treasurer',   1, 1, 0),
        ('viewer@mzugoss.com', None,          1, 0, 0),
    ]


def test_attaches_reports_and_logs_to_group(migrated_legacy_db):
    conn = migrated_legacy_db
    group_id = _rows(conn, 'SELECT id FROM groups')[0][0]
    assert _rows(conn, 'SELECT DISTINCT group_id FROM generated_reports') == [(group_id,)]
    assert _rows(conn, 'SELECT DISTINCT group_id FROM report_access_logs') == [(group_id,)]
