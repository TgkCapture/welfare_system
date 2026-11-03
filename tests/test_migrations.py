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


# ==================== INSTALLS FROM BEFORE MIGRATIONS ====================
# Tables exactly as db.create_all() made them in the versions Mzugoss may be
# running. Upgrading them is `flask db stamp 365dc0d4aa41` then `flask db upgrade`.

_CREATE_ALL_2_0_0 = """
CREATE TABLE users (id INTEGER NOT NULL, email VARCHAR(100) NOT NULL, password VARCHAR(100) NOT NULL,
    role VARCHAR(20) DEFAULT 'viewer' NOT NULL, is_active BOOLEAN, created_at DATETIME, last_login DATETIME,
    PRIMARY KEY (id), UNIQUE (email));
CREATE TABLE settings (id INTEGER NOT NULL, "key" VARCHAR(100) NOT NULL, value TEXT, updated_at DATETIME,
    PRIMARY KEY (id), UNIQUE ("key"));
CREATE TABLE generated_reports (id INTEGER NOT NULL, month INTEGER NOT NULL, year INTEGER NOT NULL,
    report_type VARCHAR(50) NOT NULL, filename VARCHAR(255) NOT NULL, file_path VARCHAR(500) NOT NULL,
    generated_by INTEGER NOT NULL, generated_at DATETIME, file_size INTEGER, total_contributions FLOAT,
    contributors_count INTEGER, defaulters_count INTEGER, money_dispensed FLOAT, total_book_balance FLOAT,
    is_archived BOOLEAN, archived_at DATETIME, PRIMARY KEY (id), FOREIGN KEY(generated_by) REFERENCES users (id));
CREATE TABLE report_access_logs (id INTEGER NOT NULL, report_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
    accessed_at DATETIME, action VARCHAR(50), PRIMARY KEY (id),
    FOREIGN KEY(report_id) REFERENCES generated_reports (id), FOREIGN KEY(user_id) REFERENCES users (id));
"""

_CREATE_ALL_2_0_2 = """
CREATE TABLE users (id INTEGER NOT NULL, email VARCHAR(150) NOT NULL, password VARCHAR(256) NOT NULL,
    role VARCHAR(20) DEFAULT 'viewer' NOT NULL, is_active BOOLEAN NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, last_login DATETIME, PRIMARY KEY (id));
CREATE UNIQUE INDEX ix_users_email ON users (email);
CREATE TABLE settings (id INTEGER NOT NULL, "key" VARCHAR(100) NOT NULL, value TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (id));
CREATE UNIQUE INDEX ix_settings_key ON settings ("key");
CREATE TABLE generated_reports (id INTEGER NOT NULL, month INTEGER NOT NULL, year INTEGER NOT NULL,
    report_type VARCHAR(50) NOT NULL, filename VARCHAR(255) NOT NULL, file_path VARCHAR(500) NOT NULL,
    generated_by INTEGER NOT NULL, generated_at DATETIME NOT NULL, file_size INTEGER, total_contributions FLOAT,
    contributors_count INTEGER, defaulters_count INTEGER, money_dispensed FLOAT, total_book_balance FLOAT,
    is_archived BOOLEAN NOT NULL, archived_at DATETIME, PRIMARY KEY (id),
    FOREIGN KEY(generated_by) REFERENCES users (id));
CREATE INDEX ix_generated_reports_is_archived ON generated_reports (is_archived);
CREATE INDEX ix_generated_reports_generated_by ON generated_reports (generated_by);
CREATE TABLE report_access_logs (id INTEGER NOT NULL, report_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
    accessed_at DATETIME NOT NULL, action VARCHAR(50) NOT NULL, PRIMARY KEY (id),
    FOREIGN KEY(report_id) REFERENCES generated_reports (id), FOREIGN KEY(user_id) REFERENCES users (id));
CREATE INDEX ix_report_access_logs_report_id ON report_access_logs (report_id);
CREATE INDEX ix_report_access_logs_user_id ON report_access_logs (user_id);
"""


@pytest.fixture(params=['2.0.0', '2.0.2'])
def migrated_old_install(request, tmp_path):
    import sqlite3

    from flask_migrate import stamp

    path = tmp_path / 'old.db'
    raw = sqlite3.connect(path)
    raw.executescript({'2.0.0': _CREATE_ALL_2_0_0, '2.0.2': _CREATE_ALL_2_0_2}[request.param])
    nulls = request.param == '2.0.0'      # 2.0.0 allowed NULL in these columns
    raw.executescript(f"""
        INSERT INTO users (id, email, password, role, is_active, created_at) VALUES
            (1, 'chair@mzugoss.com', 'hash', 'admin', 1, '2025-01-01'),
            (2, 'clerk@mzugoss.com', 'hash', 'clerk', {'NULL' if nulls else 1}, '2025-01-01'),
            (3, 'viewer@mzugoss.com', 'hash', 'viewer', 1, '2025-01-01');
        INSERT INTO settings (key, value) VALUES ('google_sheets_url', 'https://docs.google.com/spreadsheets/d/abc');
        INSERT INTO generated_reports (id, month, year, report_type, filename, file_path, generated_by,
            generated_at, is_archived) VALUES
            (1, 3, 2026, 'contributions', 'r.pdf', '/r.pdf', 1, {'NULL' if nulls else "'2026-03-31'"},
             {'NULL' if nulls else 0}),
            (2, 3, 2026, 'contributions', 'gone.pdf', '/gone.pdf', 99, '2026-03-31', 0);
        INSERT INTO report_access_logs (report_id, user_id, accessed_at, action) VALUES
            (1, 1, '2026-03-31', {'NULL' if nulls else "'download'"}), (2, 99, '2026-03-31', 'download');
    """)
    raw.commit()
    raw.close()

    app = create_app('testing', {'SQLALCHEMY_DATABASE_URI': f'sqlite:///{path}',
                                 'LOGS_FOLDER': str(tmp_path / 'logs')})
    with app.app_context():
        from app.extensions import db

        stamp(directory=MIGRATIONS, revision=BASELINE)
        upgrade(directory=MIGRATIONS)
        with db.engine.connect() as conn:
            yield conn


def test_old_installs_upgrade_with_their_officers_and_reports(migrated_old_install):
    conn = migrated_old_install
    assert _rows(conn, """
        SELECT u.email, r.name, u.is_active FROM users u LEFT JOIN roles r ON r.id = u.role_id ORDER BY u.id
    """) == [('chair@mzugoss.com', 'Chairperson', 1), ('clerk@mzugoss.com', 'Treasurer', 1),
             ('viewer@mzugoss.com', None, 0)]
    assert _rows(conn, 'SELECT google_sheet_url FROM group_settings') == [
        ('https://docs.google.com/spreadsheets/d/abc',)]

    # Missing values are filled in; rows pointing at a deleted officer are dropped
    [(generated_at, is_archived)] = _rows(conn, 'SELECT generated_at, is_archived FROM generated_reports')
    assert generated_at is not None and is_archived == 0
    assert len(_rows(conn, "SELECT action FROM report_access_logs WHERE action IS NOT NULL")) == 1


def test_old_installs_end_up_with_the_current_schema(migrated_old_install):
    from alembic.script import ScriptDirectory

    conn = migrated_old_install
    assert _rows(conn, 'SELECT version_num FROM alembic_version') == [
        (ScriptDirectory(MIGRATIONS).get_current_head(),)]
    assert _rows(conn, "SELECT name FROM sqlite_master WHERE substr(name, 1, 1) = '_'") == []
    assert _rows(conn, 'PRAGMA foreign_key_check') == []
    links = {row[3]: row[6] for row in _rows(conn, 'PRAGMA foreign_key_list(generated_reports)')}
    assert links['generated_by'] == 'SET NULL'
