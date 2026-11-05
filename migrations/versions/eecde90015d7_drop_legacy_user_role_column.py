"""drop legacy user role column

Permissions now come from the officer's group role (users.role_id), so
the old admin/clerk/viewer string is removed.

Downgrade restores the column, deriving it from the group role:
manage_users → admin, upload_data → clerk, anything else → viewer.

Revision ID: eecde90015d7
Revises: 808c6b6f7843
Create Date: 2026-11-01 22:50:24.104552

"""
import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'eecde90015d7'
down_revision = '808c6b6f7843'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('role')


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('role', sa.VARCHAR(length=20), server_default=sa.text("'viewer'"), nullable=False))

    conn = op.get_bind()
    for role_id, permissions in conn.execute(sa.text('SELECT id, permissions FROM roles')).all():
        perms = json.loads(permissions) if isinstance(permissions, str) else (permissions or [])
        legacy = 'admin' if 'manage_users' in perms else 'clerk' if 'upload_data' in perms else 'viewer'
        conn.execute(
            sa.text('UPDATE users SET role = :role WHERE role_id = :rid'),
            {'role': legacy, 'rid': role_id},
        )
