"""setup checklist

A setup checklist walks a new group through branding, payout purposes, its
workbook, the first sync, rules, the public page and officers. Groups that
already exist are running, so their checklist starts hidden (officers can
still open it at /setup).

Revision ID: 191c98a5790f
Revises: 0a94e0dbf35b
Create Date: 2026-11-02 18:41:19.108854

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '191c98a5790f'
down_revision = '0a94e0dbf35b'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('group_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('setup_marks', sa.JSON(), server_default=sa.text("'[]'"), nullable=False))
        batch_op.add_column(sa.Column('setup_dismissed', sa.Boolean(), server_default=sa.false(), nullable=False))

    op.execute(sa.text('UPDATE group_settings SET setup_dismissed = :yes').bindparams(yes=True))


def downgrade():
    with op.batch_alter_table('group_settings', schema=None) as batch_op:
        batch_op.drop_column('setup_dismissed')
        batch_op.drop_column('setup_marks')
