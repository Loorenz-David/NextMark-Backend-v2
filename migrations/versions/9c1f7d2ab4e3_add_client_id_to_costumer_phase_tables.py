"""add client_id to costumer phase tables

Revision ID: 9c1f7d2ab4e3
Revises: 8f6b5f0bb6d1
Create Date: 2026-03-02 13:05:00.000000
"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9c1f7d2ab4e3"
down_revision = "8f6b5f0bb6d1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("costumer", sa.Column("client_id", sa.String(), nullable=True))
    op.create_index("ix_costumer_client_id", "costumer", ["client_id"], unique=False)

    op.add_column("costumer_address", sa.Column("client_id", sa.String(), nullable=True))
    op.create_index(
        "ix_costumer_address_client_id",
        "costumer_address",
        ["client_id"],
        unique=False,
    )

    op.add_column("costumer_phone", sa.Column("client_id", sa.String(), nullable=True))
    op.create_index(
        "ix_costumer_phone_client_id",
        "costumer_phone",
        ["client_id"],
        unique=False,
    )

    op.add_column(
        "costumer_operating_hours",
        sa.Column("client_id", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_costumer_operating_hours_client_id",
        "costumer_operating_hours",
        ["client_id"],
        unique=False,
    )

    op.add_column("order_delivery_window", sa.Column("client_id", sa.String(), nullable=True))
    op.create_index(
        "ix_order_delivery_window_client_id",
        "order_delivery_window",
        ["client_id"],
        unique=False,
    )

    _backfill_client_ids("costumer", "costumer")
    _backfill_client_ids("costumer_address", "costumer_address")
    _backfill_client_ids("costumer_phone", "costumer_phone")
    _backfill_client_ids("costumer_operating_hours", "costumer_operating_hours")
    _backfill_client_ids("order_delivery_window", "order_delivery_window")


def downgrade():
    op.drop_index("ix_order_delivery_window_client_id", table_name="order_delivery_window")
    op.drop_column("order_delivery_window", "client_id")

    op.drop_index(
        "ix_costumer_operating_hours_client_id",
        table_name="costumer_operating_hours",
    )
    op.drop_column("costumer_operating_hours", "client_id")

    op.drop_index("ix_costumer_phone_client_id", table_name="costumer_phone")
    op.drop_column("costumer_phone", "client_id")

    op.drop_index("ix_costumer_address_client_id", table_name="costumer_address")
    op.drop_column("costumer_address", "client_id")

    op.drop_index("ix_costumer_client_id", table_name="costumer")
    op.drop_column("costumer", "client_id")


def _backfill_client_ids(table_name: str, label: str) -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(f"SELECT id FROM {table_name} WHERE client_id IS NULL"),
    ).fetchall()
    for row in rows:
        generated = f"{label}_{uuid4().hex}"
        bind.execute(
            sa.text(f"UPDATE {table_name} SET client_id = :client_id WHERE id = :id"),
            {"client_id": generated, "id": row[0]},
        )

