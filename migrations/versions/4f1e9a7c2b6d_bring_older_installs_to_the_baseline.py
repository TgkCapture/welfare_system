"""bring older installs to the baseline

Installs from before migrations (2.0.x and earlier) created their tables
with db.create_all(), and the result depends on the version: 2.0.0 has no
named indexes or constraints, no index on users.email, shorter email and
password columns, and allows NULL where the baseline requires a value.
Later migrations drop and rebuild indexes and constraints by name, so they
fail on such a database.

After `flask db stamp 365dc0d4aa41`, this rebuilds the four original tables
exactly as the baseline migration creates them and copies every row
across, filling missing values (is_active and is_archived default to the
old app's defaults; missing timestamps become the time of the upgrade).
Report and access-log rows that point at a user or report which no longer
exists are dropped: the old app didn't enforce those links, and the
database will from now on.

A database that already matches the baseline (a new install, or one made
by these migrations) is left alone. There is nothing to undo on downgrade.

Revision ID: 4f1e9a7c2b6d
Revises: 365dc0d4aa41
Create Date: 2026-11-03 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4f1e9a7c2b6d'
down_revision = '365dc0d4aa41'
branch_labels = None
depends_on = None

_TABLES = ('users', 'settings', 'generated_reports', 'report_access_logs')   # parents first

# Names the baseline gives; an older install is missing some of them
_EXPECTED = {
    'users': {'indexes': {'ix_users_email'}, 'fks': set()},
    'settings': {'indexes': {'ix_settings_key'}, 'fks': set()},
    'generated_reports': {'indexes': {'ix_generated_reports_generated_by', 'ix_generated_reports_is_archived'},
                          'fks': {'fk_generated_reports_generated_by_users'}},
    'report_access_logs': {'indexes': {'ix_report_access_logs_report_id', 'ix_report_access_logs_user_id'},
                           'fks': {'fk_report_access_logs_report_id_generated_reports',
                                   'fk_report_access_logs_user_id_users'}},
}


def _matches_baseline(inspector):
    for table, expected in _EXPECTED.items():
        indexes = {i['name'] for i in inspector.get_indexes(table)}
        fks = {f['name'] for f in inspector.get_foreign_keys(table)}
        if not (expected['indexes'] <= indexes and expected['fks'] <= fks):
            return False
    return True


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not set(_TABLES) <= set(inspector.get_table_names()) or _matches_baseline(inspector):
        return

    old_columns = {t: {c['name'] for c in inspector.get_columns(t)} for t in _TABLES}
    for table in _TABLES:
        # Indexes keep their names when a table is renamed; 2.0.2 already has
        # some of the baseline's, which the new tables need
        for index in inspector.get_indexes(table):
            if (index['name'] or '').startswith('ix_'):
                op.drop_index(index['name'], table_name=table)
        op.rename_table(table, f'_legacy_{table}')
    _create_baseline_tables()

    old = {t: sa.table(f'_legacy_{t}', *[sa.column(c) for c in old_columns[t]]) for t in _TABLES}
    now = sa.func.current_timestamp()

    def col(table, name, fallback=None):
        """The old column, or *fallback* if this version didn't have it."""
        if name in old_columns[table]:
            column = old[table].c[name]
            return column if fallback is None else sa.func.coalesce(column, fallback)
        return fallback if fallback is not None else sa.null()

    _copy(bind, 'users', {
        'id': col('users', 'id'), 'email': col('users', 'email'), 'password': col('users', 'password'),
        'role': col('users', 'role', sa.literal('viewer')), 'is_active': col('users', 'is_active', sa.true()),
        'created_at': col('users', 'created_at', now), 'last_login': col('users', 'last_login'),
    }, old['users'])
    _copy(bind, 'settings', {
        'id': col('settings', 'id'), 'key': col('settings', 'key'), 'value': col('settings', 'value'),
        'updated_at': col('settings', 'updated_at'),
    }, old['settings'])

    users = sa.select(old['users'].c.id)
    reports = old['generated_reports']
    _copy(bind, 'generated_reports', {
        **{name: col('generated_reports', name) for name in (
            'id', 'month', 'year', 'filename', 'file_path', 'generated_by', 'file_size', 'total_contributions',
            'contributors_count', 'defaulters_count', 'money_dispensed', 'total_book_balance', 'archived_at')},
        'report_type': col('generated_reports', 'report_type', sa.literal('contributions')),
        'generated_at': col('generated_reports', 'generated_at', now),
        'is_archived': col('generated_reports', 'is_archived', sa.false()),
    }, reports, reports.c.generated_by.in_(users))

    logs = old['report_access_logs']
    _copy(bind, 'report_access_logs', {
        'id': col('report_access_logs', 'id'), 'report_id': col('report_access_logs', 'report_id'),
        'user_id': col('report_access_logs', 'user_id'),
        'accessed_at': col('report_access_logs', 'accessed_at', now),
        'action': col('report_access_logs', 'action', sa.literal('view')),
    }, logs, logs.c.user_id.in_(users),
        logs.c.report_id.in_(sa.select(reports.c.id).where(reports.c.generated_by.in_(users))))

    for table in reversed(_TABLES):
        op.drop_table(f'_legacy_{table}')

    if bind.dialect.name == 'postgresql':
        for table in _TABLES:
            op.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                       f"COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)")


def downgrade():
    pass


def _copy(bind, table, values, source, *where):
    target = sa.table(table, *[sa.column(name) for name in values])
    query = sa.select(*[expr.label(name) for name, expr in values.items()]).select_from(source)
    if where:
        query = query.where(*where)
    bind.execute(target.insert().from_select(list(values), query))


def _create_baseline_tables():
    """The tables exactly as revision 365dc0d4aa41 creates them."""
    op.create_table('settings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('key', sa.String(length=100), nullable=False),
    sa.Column('value', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_settings_key'), ['key'], unique=True)

    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=150), nullable=False),
    sa.Column('password', sa.String(length=256), nullable=False),
    sa.Column('role', sa.String(length=20), server_default='viewer', nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('last_login', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)

    op.create_table('generated_reports',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('month', sa.Integer(), nullable=False),
    sa.Column('year', sa.Integer(), nullable=False),
    sa.Column('report_type', sa.String(length=50), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('file_path', sa.String(length=500), nullable=False),
    sa.Column('generated_by', sa.Integer(), nullable=False),
    sa.Column('generated_at', sa.DateTime(), nullable=False),
    sa.Column('file_size', sa.Integer(), nullable=True),
    sa.Column('total_contributions', sa.Float(), nullable=True),
    sa.Column('contributors_count', sa.Integer(), nullable=True),
    sa.Column('defaulters_count', sa.Integer(), nullable=True),
    sa.Column('money_dispensed', sa.Float(), nullable=True),
    sa.Column('total_book_balance', sa.Float(), nullable=True),
    sa.Column('is_archived', sa.Boolean(), nullable=False),
    sa.Column('archived_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['generated_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('generated_reports', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_generated_reports_generated_by'), ['generated_by'], unique=False)
        batch_op.create_index(batch_op.f('ix_generated_reports_is_archived'), ['is_archived'], unique=False)

    op.create_table('report_access_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('report_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('accessed_at', sa.DateTime(), nullable=False),
    sa.Column('action', sa.String(length=50), nullable=False),
    sa.ForeignKeyConstraint(['report_id'], ['generated_reports.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('report_access_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_report_access_logs_report_id'), ['report_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_report_access_logs_user_id'), ['user_id'], unique=False)
