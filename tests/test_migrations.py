"""
Runs the real Alembic migrations against a file database seeded the way
an existing single-group Mzugoss install looks before step 1a.
"""
import json
import os

import pytest
import sqlalchemy as sa
from flask_migrate import downgrade, upgrade

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


def test_seeds_default_payout_purposes(migrated_legacy_db):
    assert sorted(_rows(migrated_legacy_db, 'SELECT name, is_active FROM payout_purposes')) == [
        ('Funeral condolence', 1), ('Sick patient grant', 1), ('Wedding gift', 1),
    ]


def test_existing_groups_get_an_access_code_that_is_on(migrated_legacy_db):
    [(code, enabled, paid_enabled)] = _rows(
        migrated_legacy_db, 'SELECT access_code, access_code_enabled, public_paid_enabled FROM group_settings')
    assert len(code) == 6 and enabled and paid_enabled


def test_existing_groups_start_with_the_setup_checklist_hidden(migrated_legacy_db):
    assert _rows(migrated_legacy_db, 'SELECT setup_dismissed, setup_marks FROM group_settings') == [(1, '[]')]


def test_seeds_mzugoss_welfare_rules(migrated_legacy_db):
    titles = [t for (t,) in _rows(migrated_legacy_db, 'SELECT title FROM rule_sections ORDER BY position')]
    assert titles[:3] == ['Quick summary', 'Who can receive support', 'Funeral support']
    assert len(titles) == 9


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


def test_legacy_role_column_is_dropped(migrated_legacy_db):
    columns = {row[1] for row in _rows(migrated_legacy_db, 'PRAGMA table_info(users)')}
    assert 'role' not in columns
    assert {'group_id', 'role_id', 'is_superadmin'} <= columns


def test_upgrade_is_committed_cleanly(migrated_legacy_db):
    """Batch mode rebuilds SQLite tables; a migration that isn't committed
    leaves temporary tables behind and the old revision recorded."""
    from alembic.script import ScriptDirectory

    conn = migrated_legacy_db
    head = ScriptDirectory(MIGRATIONS).get_current_head()
    assert _rows(conn, 'SELECT version_num FROM alembic_version') == [(head,)]
    assert _rows(conn, "SELECT name FROM sqlite_master WHERE name LIKE '_alembic_tmp%'") == []
    assert _rows(conn, 'PRAGMA foreign_key_check') == []


def test_records_keep_their_officer_link_until_the_officer_is_deleted(migrated_legacy_db):
    for table, column in (('generated_reports', 'generated_by'), ('report_access_logs', 'user_id'),
                          ('sync_runs', 'synced_by'), ('period_summaries', 'synced_by')):
        links = {row[3]: row[6] for row in _rows(migrated_legacy_db, f'PRAGMA foreign_key_list({table})')}
        assert links[column] == 'SET NULL', table


def test_downgrade_restores_legacy_roles(migrated_legacy_db):
    from app.extensions import db
    migrated_legacy_db.close()

    downgrade(directory=MIGRATIONS, revision='808c6b6f7843')

    with db.engine.connect() as conn:
        assert _rows(conn, 'SELECT email, role FROM users ORDER BY id') == [
            ('admin@mzugoss.com', 'admin'),
            ('clerk@mzugoss.com', 'clerk'),
            ('viewer@mzugoss.com', 'viewer'),
        ]


def test_attaches_reports_and_logs_to_group(migrated_legacy_db):
    conn = migrated_legacy_db
    group_id = _rows(conn, 'SELECT id FROM groups')[0][0]
    assert _rows(conn, 'SELECT DISTINCT group_id FROM generated_reports') == [(group_id,)]
    assert _rows(conn, 'SELECT DISTINCT group_id FROM report_access_logs') == [(group_id,)]
