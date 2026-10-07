"""add event link and entity columns to order_audit_log

Field-level edit history is written to order_audit_log by every order and item
edit path. Each row carries the uuid of the order event it belongs to so the
event history can show what changed inside that event, plus the entity it
describes (order field, item, note) with a label snapshot that survives the
item being deleted. All columns are nullable: the table has never been written.

Revision ID: a7b8c9d0e1f2
Revises: f4a5b6c7d8e9
Create Date: 2026-10-07 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "a7b8c9d0e1f2"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None

TABLE = "order_audit_log"
EVENT_ID_INDEX = "ix_order_audit_log_event_id"
NEW_COLUMNS = ("event_id", "entity_type", "entity_id", "entity_label")


def _has_column(table: str, column: str) -> bool:
    inspector = inspect(op.get_bind())
    return any(c["name"] == column for c in inspector.get_columns(table))


def _has_index(table: str, index: str) -> bool:
    inspector = inspect(op.get_bind())
    return any(i["name"] == index for i in inspector.get_indexes(table))


def upgrade() -> None:
    for column in NEW_COLUMNS:
        if not _has_column(TABLE, column):
            with op.batch_alter_table(TABLE, schema=None) as batch_op:
                batch_op.add_column(sa.Column(column, sa.String(), nullable=True))

    if not _has_index(TABLE, EVENT_ID_INDEX):
        with op.batch_alter_table(TABLE, schema=None) as batch_op:
            batch_op.create_index(
                batch_op.f(EVENT_ID_INDEX),
                ["event_id"],
                unique=False,
            )


def downgrade() -> None:
    if _has_index(TABLE, EVENT_ID_INDEX):
        with op.batch_alter_table(TABLE, schema=None) as batch_op:
            batch_op.drop_index(batch_op.f(EVENT_ID_INDEX))

    for column in reversed(NEW_COLUMNS):
        if _has_column(TABLE, column):
            with op.batch_alter_table(TABLE, schema=None) as batch_op:
                batch_op.drop_column(column)
