"""Add external_tracking_number and external_tracking_link to order table.
Backfills tracking_number, tracking_link, and tracking_token_hash for all
existing orders that were created before automatic generation was added.

Revision ID: r6s2t9u4v8w3
Revises: q5r1s8t3u7v2
Create Date: 2025-01-01 00:00:01.000000

"""

import hashlib
import os
import secrets
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision = "r6s2t9u4v8w3"
down_revision = "q5r1s8t3u7v2"
branch_labels = None
depends_on = None

TRACKING_ORDER_BASE_URL = os.environ.get(
    "TRACKING_ORDER_BASE_URL", "https://tracking.nextmark.app"
)
_BATCH_SIZE = 100


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(c["name"] == column for c in inspector.get_columns(table))


def _backfill_tracking_identifiers(bind) -> None:
    """Generate tracking_number / tracking_link / tracking_token_hash for every
    order row that is still missing them.  Runs inside the migration transaction.
    """
    now = datetime.now(timezone.utc)

    # Fetch ids of all orders that still need backfilling.
    result = bind.execute(
        text(
            "SELECT id, order_scalar_id FROM \"order\" "
            "WHERE tracking_token_hash IS NULL"
        )
    )
    rows = result.fetchall()

    for i in range(0, len(rows), _BATCH_SIZE):
        batch = rows[i : i + _BATCH_SIZE]
        for row in batch:
            order_id = row[0]
            scalar_id = row[1] or row[0]  # fall back to pk if scalar_id not set

            raw_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
            tracking_number = f"TRK-{scalar_id}"
            tracking_link = f"{TRACKING_ORDER_BASE_URL}/track/{raw_token}"

            bind.execute(
                text(
                    "UPDATE \"order\" SET "
                    "  tracking_number = :tn, "
                    "  tracking_link = :tl, "
                    "  tracking_token_hash = :th, "
                    "  tracking_token_created_at = :ts "
                    "WHERE id = :id"
                ),
                {
                    "tn": tracking_number,
                    "tl": tracking_link,
                    "th": token_hash,
                    "ts": now,
                    "id": order_id,
                },
            )

        print(
            f"[backfill] processed {min(i + _BATCH_SIZE, len(rows))}/{len(rows)} orders"
        )


def upgrade():
    if not _has_column("order", "external_tracking_number"):
        op.add_column(
            "order",
            sa.Column("external_tracking_number", sa.String(), nullable=True),
        )
        op.create_index(
            "ix_order_external_tracking_number",
            "order",
            ["external_tracking_number"],
        )

    if not _has_column("order", "external_tracking_link"):
        op.add_column(
            "order",
            sa.Column("external_tracking_link", sa.String(), nullable=True),
        )
        op.create_index(
            "ix_order_external_tracking_link",
            "order",
            ["external_tracking_link"],
        )

    # Backfill tracking identifiers for all existing orders.
    bind = op.get_bind()
    _backfill_tracking_identifiers(bind)


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = {idx["name"] for idx in inspector.get_indexes("order")}
    columns = {c["name"] for c in inspector.get_columns("order")}

    if "ix_order_external_tracking_link" in indexes:
        op.drop_index("ix_order_external_tracking_link", table_name="order")
    if "external_tracking_link" in columns:
        op.drop_column("order", "external_tracking_link")

    if "ix_order_external_tracking_number" in indexes:
        op.drop_index("ix_order_external_tracking_number", table_name="order")
    if "external_tracking_number" in columns:
        op.drop_column("order", "external_tracking_number")
