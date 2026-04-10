"""Fix missing relayed_at column on plan_event table.

The previous migration (g3h9k2m5n1x8) incorrectly referenced the table as
'delivery_plan_event' but the actual table name is 'plan_event'.

Revision ID: h1j4k7m2n9p0
Revises: g3h9k2m5n1x8
Create Date: 2026-03-18 13:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'h1j4k7m2n9p0'
down_revision = 'g3h9k2m5n1x8'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_context().bind
    inspector = inspect(connection)
    existing_tables = inspector.get_table_names()

    if 'plan_event' in existing_tables:
        columns = [col['name'] for col in inspector.get_columns('plan_event')]
        if 'relayed_at' not in columns:
            op.add_column(
                'plan_event',
                sa.Column('relayed_at', sa.DateTime(timezone=True), nullable=True)
            )
            op.create_index('ix_plan_event_relayed_at', 'plan_event', ['relayed_at'])


def downgrade():
    connection = op.get_context().bind
    inspector = inspect(connection)
    existing_tables = inspector.get_table_names()

    if 'plan_event' in existing_tables:
        columns = [col['name'] for col in inspector.get_columns('plan_event')]
        if 'relayed_at' in columns:
            op.drop_index('ix_plan_event_relayed_at', table_name='plan_event')
            op.drop_column('plan_event', 'relayed_at')
