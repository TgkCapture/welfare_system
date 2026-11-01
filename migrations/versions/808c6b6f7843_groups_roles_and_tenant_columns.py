"""groups, roles and tenant columns

Adds groups, per-group settings and group-scoped roles, and gives users,
reports and access logs a group_id. Email becomes unique per group.

Data migration: if the database already holds users or reports (an
existing single-group Mzugoss install), a "Mzugoss" group is created with
the preset roles, and all existing rows are attached to it:

  - admin  → Chairperson
  - clerk  → Treasurer
  - viewer → deactivated (members no longer have accounts)

The Google Sheet URL and retention days are copied from the global
settings table into the group's settings. The old keys are left in place
until step 1e stops reading them.

Downgrade drops the new tables and columns. Viewer deactivation is not
reversed.

Revision ID: 808c6b6f7843
Revises: 365dc0d4aa41
Create Date: 2026-11-01 22:10:03.612052

"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '808c6b6f7843'
down_revision = '365dc0d4aa41'
branch_labels = None
depends_on = None


# Frozen copy of the presets at the time of this migration — migrations
# must not import app code, which keeps changing.
_PRESET_ROLES = {
    'Chairperson': [
        'upload_data', 'generate_reports', 'manage_reports', 'view_reports',
        'manage_members', 'edit_rules', 'edit_settings', 'manage_users',
    ],
    'Treasurer': [
        'upload_data', 'generate_reports', 'manage_reports',
        'view_reports', 'manage_members',
    ],
    'Secretary': ['generate_reports', 'view_reports', 'edit_rules'],
}
_LEGACY_ROLE_PRESETS = {'admin': 'Chairperson', 'clerk': 'Treasurer'}

_groups = sa.table(
    'groups',
    sa.column('id', sa.Integer), sa.column('name', sa.String),
    sa.column('slug', sa.String), sa.column('is_active', sa.Boolean),
    sa.column('created_at', sa.DateTime),
)
_group_settings = sa.table(
    'group_settings',
    sa.column('group_id', sa.Integer), sa.column('display_name', sa.String),
    sa.column('short_name', sa.String), sa.column('primary_color', sa.String),
    sa.column('report_title', sa.String), sa.column('currency', sa.String),
    sa.column('google_sheet_url', sa.String), sa.column('upload_enabled', sa.Boolean),
    sa.column('report_retention_days', sa.Integer), sa.column('updated_at', sa.DateTime),
)
_roles = sa.table(
    'roles',
    sa.column('id', sa.Integer), sa.column('group_id', sa.Integer),
    sa.column('name', sa.String), sa.column('permissions', sa.JSON),
    sa.column('created_at', sa.DateTime),
)
_users = sa.table(
    'users',
    sa.column('group_id', sa.Integer), sa.column('role_id', sa.Integer),
    sa.column('role', sa.String), sa.column('is_active', sa.Boolean),
)
_settings = sa.table('settings', sa.column('key', sa.String), sa.column('value', sa.Text))


def upgrade():
    # ── 1. New tables ────────────────────────────────────────────────
    op.create_table('groups',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('slug', sa.String(length=60), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_groups'))
    )
    with op.batch_alter_table('groups', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_groups_slug'), ['slug'], unique=True)

    op.create_table('group_settings',
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.Column('display_name', sa.String(length=150), nullable=False),
    sa.Column('short_name', sa.String(length=30), nullable=True),
    sa.Column('logo_path', sa.String(length=255), nullable=True),
    sa.Column('primary_color', sa.String(length=7), nullable=False),
    sa.Column('report_title', sa.String(length=200), nullable=True),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('google_sheet_url', sa.String(length=500), nullable=True),
    sa.Column('upload_enabled', sa.Boolean(), nullable=False),
    sa.Column('report_retention_days', sa.Integer(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['groups.id'], name=op.f('fk_group_settings_group_id_groups')),
    sa.PrimaryKeyConstraint('group_id', name=op.f('pk_group_settings'))
    )
    op.create_table('roles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.Column('permissions', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['groups.id'], name=op.f('fk_roles_group_id_groups')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_roles')),
    sa.UniqueConstraint('group_id', 'name', name='uq_roles_group_name')
    )
    with op.batch_alter_table('roles', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_roles_group_id'), ['group_id'], unique=False)

    # ── 2. New columns, nullable until backfilled ────────────────────
    with op.batch_alter_table('generated_reports', schema=None) as batch_op:
        batch_op.add_column(sa.Column('group_id', sa.Integer(), nullable=True))

    with op.batch_alter_table('report_access_logs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('group_id', sa.Integer(), nullable=True))

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('group_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('role_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('is_superadmin', sa.Boolean(), server_default=sa.text('0'), nullable=False))
        batch_op.drop_index(batch_op.f('ix_users_email'))
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=False)
        batch_op.create_index(batch_op.f('ix_users_group_id'), ['group_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_users_role_id'), ['role_id'], unique=False)
        batch_op.create_unique_constraint('uq_users_group_email', ['group_id', 'email'])
        batch_op.create_foreign_key(batch_op.f('fk_users_role_id_roles'), 'roles', ['role_id'], ['id'])
        batch_op.create_foreign_key(batch_op.f('fk_users_group_id_groups'), 'groups', ['group_id'], ['id'])

    # ── 3. Move an existing single-group install into a Mzugoss group ─
    conn = op.get_bind()
    has_data = conn.execute(sa.text(
        'SELECT (SELECT COUNT(*) FROM users) + (SELECT COUNT(*) FROM generated_reports)'
    )).scalar()
    if has_data:
        _migrate_existing_install(conn)

    # ── 4. Reports and logs always belong to a group ─────────────────
    with op.batch_alter_table('generated_reports', schema=None) as batch_op:
        batch_op.alter_column('group_id', existing_type=sa.Integer(), nullable=False)
        batch_op.create_index(batch_op.f('ix_generated_reports_group_id'), ['group_id'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_generated_reports_group_id_groups'), 'groups', ['group_id'], ['id'])

    with op.batch_alter_table('report_access_logs', schema=None) as batch_op:
        batch_op.alter_column('group_id', existing_type=sa.Integer(), nullable=False)
        batch_op.create_index(batch_op.f('ix_report_access_logs_group_id'), ['group_id'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_report_access_logs_group_id_groups'), 'groups', ['group_id'], ['id'])


def _migrate_existing_install(conn):
    now = datetime.utcnow()
    old = dict(conn.execute(sa.select(_settings.c.key, _settings.c.value)).all())

    conn.execute(_groups.insert().values(
        name='Mzugoss Class of 2018', slug='mzugoss', is_active=True, created_at=now,
    ))
    group_id = conn.execute(
        sa.select(_groups.c.id).where(_groups.c.slug == 'mzugoss')
    ).scalar_one()

    retention = old.get('report_retention_days')
    conn.execute(_group_settings.insert().values(
        group_id=group_id,
        display_name='Mzugoss Class of 2018',
        short_name='Mzugoss',
        primary_color='#1d4ed8',
        report_title='MZUGOSS CLASS OF 2018 - MONTHLY CONTRIBUTIONS REPORT',
        currency='MWK',
        google_sheet_url=old.get('google_sheets_url') or None,
        upload_enabled=True,
        report_retention_days=int(retention) if retention and retention.isdigit() else None,
        updated_at=now,
    ))

    for name, permissions in _PRESET_ROLES.items():
        conn.execute(_roles.insert().values(
            group_id=group_id, name=name, permissions=permissions, created_at=now,
        ))
    role_ids = dict(conn.execute(
        sa.select(_roles.c.name, _roles.c.id).where(_roles.c.group_id == group_id)
    ).all())

    conn.execute(_users.update().values(group_id=group_id))
    for legacy, preset in _LEGACY_ROLE_PRESETS.items():
        conn.execute(
            _users.update().where(_users.c.role == legacy).values(role_id=role_ids[preset])
        )
    conn.execute(_users.update().where(_users.c.role == 'viewer').values(is_active=False))

    for table in ('generated_reports', 'report_access_logs'):
        conn.execute(sa.text(f'UPDATE {table} SET group_id = :gid'), {'gid': group_id})


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_users_group_id_groups'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('fk_users_role_id_roles'), type_='foreignkey')
        batch_op.drop_constraint('uq_users_group_email', type_='unique')
        batch_op.drop_index(batch_op.f('ix_users_role_id'))
        batch_op.drop_index(batch_op.f('ix_users_group_id'))
        batch_op.drop_index(batch_op.f('ix_users_email'))
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)
        batch_op.drop_column('is_superadmin')
        batch_op.drop_column('role_id')
        batch_op.drop_column('group_id')

    with op.batch_alter_table('report_access_logs', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_report_access_logs_group_id_groups'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_report_access_logs_group_id'))
        batch_op.drop_column('group_id')

    with op.batch_alter_table('generated_reports', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_generated_reports_group_id_groups'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_generated_reports_group_id'))
        batch_op.drop_column('group_id')

    with op.batch_alter_table('roles', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_roles_group_id'))

    op.drop_table('roles')
    op.drop_table('group_settings')
    with op.batch_alter_table('groups', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_groups_slug'))

    op.drop_table('groups')
