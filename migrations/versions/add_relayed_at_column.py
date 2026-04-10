"""Add relayed_at column to event tables for deduplication tracking.

Revision ID: g3h9k2m5n1x8
Revises: f91a6e8c2d4b
Create Date: 2026-03-18 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'g3h9k2m5n1x8'
down_revision = 'f91a6e8c2d4b'
branch_labels = None
depends_on = None


def upgrade():
    """Add relayed_at column to event tables that exist."""
    from sqlalchemy import inspect, MetaData, Table
    
    event_tables = [
        'order_event',
        'plan_event',  # delivery_plan_event model uses __tablename__ = 'plan_event'
        'local_delivery_plan_event',
        'route_solution_event',
        'route_solution_stop_event',
        'app_event_outbox',
    ]
    
    # Get connection to check which tables exist
    connection = op.get_context().bind
    inspector = inspect(connection)
    existing_tables = inspector.get_table_names()
    
    for table_name in event_tables:
        # Only add column if table exists and column doesn't already exist
        if table_name in existing_tables:
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            if 'relayed_at' not in columns:
                op.add_column(
                    table_name,
                    sa.Column('relayed_at', sa.DateTime(timezone=True), nullable=True, index=True)
                )
                print(f"✓ Added relayed_at column to {table_name}")
            else:
                print(f"✓ relayed_at column already exists in {table_name}")
        else:
            print(f"⚠ Table {table_name} does not exist, skipping")


def downgrade():
    """Remove relayed_at column from event tables."""
    from sqlalchemy import inspect
    
    event_tables = [
        'order_event',
        'plan_event',  # delivery_plan_event model uses __tablename__ = 'plan_event'
        'local_delivery_plan_event',
        'route_solution_event',
        'route_solution_stop_event',
        'app_event_outbox',
    ]
    
    connection = op.get_context().bind
    inspector = inspect(connection)
    existing_tables = inspector.get_table_names()
    
    for table_name in event_tables:
        if table_name in existing_tables:
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            if 'relayed_at' in columns:
                op.drop_column(table_name, 'relayed_at')
                print(f"✓ Dropped relayed_at column from {table_name}")
        else:
            print(f"⚠ Table {table_name} does not exist, skipping")
