"""mark legacy backfilled events dispatched

Revision ID: e4c2b9a17d55
Revises: d3f1a7c9b2e4
Create Date: 2026-03-14 23:59:30.000000
"""

from alembic import op


revision = "e4c2b9a17d55"
down_revision = "d3f1a7c9b2e4"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE order_event
        SET
            dispatch_status = 'DISPATCHED',
            claimed_at = NULL,
            claimed_by = NULL,
            last_error = NULL
        WHERE dispatch_status = 'PENDING'
          AND event_id LIKE 'order-event:%'
        """
    )
    op.execute(
        """
        UPDATE plan_event
        SET
            dispatch_status = 'DISPATCHED',
            claimed_at = NULL,
            claimed_by = NULL,
            last_error = NULL
        WHERE dispatch_status = 'PENDING'
          AND event_id LIKE 'plan-event:%'
        """
    )


def downgrade():
    op.execute(
        """
        UPDATE order_event
        SET dispatch_status = 'PENDING'
        WHERE dispatch_status = 'DISPATCHED'
          AND event_id LIKE 'order-event:%'
        """
    )
    op.execute(
        """
        UPDATE plan_event
        SET dispatch_status = 'PENDING'
        WHERE dispatch_status = 'DISPATCHED'
          AND event_id LIKE 'plan-event:%'
        """
    )
