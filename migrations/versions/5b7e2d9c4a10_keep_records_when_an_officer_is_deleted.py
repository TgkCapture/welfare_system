"""keep records when an officer is deleted

Reports, report access records, syncs and period summaries pointed at the
officer who made them with a foreign key that blocked deleting that
officer on Postgres. They now keep the record and clear the link.

Revision ID: 5b7e2d9c4a10
Revises: 1c2392acf221
Create Date: 2026-11-02 22:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5b7e2d9c4a10'
down_revision = '1c2392acf221'
branch_labels = None
depends_on = None

# Lets batch mode find the baseline's unnamed SQLite foreign keys by these names
NAMING = {'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s'}

# table, column, nullable before this revision
LINKS = [
    ('generated_reports', 'generated_by', False),
    ('report_access_logs', 'user_id', False),
    ('period_summaries', 'synced_by', True),
    ('sync_runs', 'synced_by', True),
]


def upgrade():
    for table, column, was_nullable in LINKS:
        name = f'fk_{table}_{column}_users'
        with op.batch_alter_table(table, naming_convention=NAMING) as batch_op:
            batch_op.drop_constraint(name, type_='foreignkey')
            if not was_nullable:
                batch_op.alter_column(column, existing_type=sa.Integer(), nullable=True)
            batch_op.create_foreign_key(name, 'users', [column], ['id'], ondelete='SET NULL')


def downgrade():
    # The columns stay nullable: rows whose officer was deleted have no one to point at
    for table, column, _ in LINKS:
        name = f'fk_{table}_{column}_users'
        with op.batch_alter_table(table, naming_convention=NAMING) as batch_op:
            batch_op.drop_constraint(name, type_='foreignkey')
            batch_op.create_foreign_key(name, 'users', [column], ['id'])
