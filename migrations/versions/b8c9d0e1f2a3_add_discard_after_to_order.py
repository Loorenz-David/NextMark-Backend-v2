"""add discard_after to order

Shopify orders whose intent says the customer took the goods at the counter
are kept as unplanned orders (no objective) so staff can correct a cashier
mistake. discard_after marks when such an order may be purged by the
scheduler if it is still unplanned. Nullable: every existing order is kept.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-10-07 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None

TABLE = "order"
COLUMN = "discard_after"
INDEX = "ix_order_discard_after"


def _has_column(table: str, column: str) -> bool:
    inspector = inspect(op.get_bind())
    return any(c["name"] == column for c in inspector.get_columns(table))


def _has_index(table: str, index: str) -> bool:
    inspector = inspect(op.get_bind())
    return any(i["name"] == index for i in inspector.get_indexes(table))


def upgrade() -> None:
    if not _has_column(TABLE, COLUMN):
        with op.batch_alter_table(TABLE, schema=None) as batch_op:
            batch_op.add_column(sa.Column(COLUMN, sa.DateTime(timezone=True), nullable=True))

    if not _has_index(TABLE, INDEX):
        with op.batch_alter_table(TABLE, schema=None) as batch_op:
            batch_op.create_index(batch_op.f(INDEX), [COLUMN], unique=False)


def downgrade() -> None:
    if _has_index(TABLE, INDEX):
        with op.batch_alter_table(TABLE, schema=None) as batch_op:
            batch_op.drop_index(batch_op.f(INDEX))

    if _has_column(TABLE, COLUMN):
        with op.batch_alter_table(TABLE, schema=None) as batch_op:
            batch_op.drop_column(COLUMN)
