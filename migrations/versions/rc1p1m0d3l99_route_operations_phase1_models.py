"""Route operations phase 1 model relabel.

Revision ID: rc1p1m0d3l99
Revises: z1a5b9c3d7e2
Create Date: 2026-03-26 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision = "rc1p1m0d3l99"
down_revision = "z1a5b9c3d7e2"
branch_labels = None
depends_on = None


def _has_table(table: str) -> bool:
    inspector = inspect(op.get_bind())
    return table in inspector.get_table_names()


def _has_column(table: str, column: str) -> bool:
    inspector = inspect(op.get_bind())
    if not _has_table(table):
        return False
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()

    if _has_table("delivery_plan") and not _has_table("route_plan"):
        op.rename_table("delivery_plan", "route_plan")

    if _has_table("route_plan") and _has_column("route_plan", "plan_type"):
        op.drop_column("route_plan", "plan_type")

    if _has_table("route_plan") and not _has_column("route_plan", "date_strategy"):
        op.add_column(
            "route_plan",
            sa.Column("date_strategy", sa.String(), nullable=True, server_default="single"),
        )
        bind.execute(text("UPDATE route_plan SET date_strategy = 'single' WHERE date_strategy IS NULL"))
        op.alter_column("route_plan", "date_strategy", nullable=False, server_default=None)

    if _has_table("route_plan") and _has_column("route_plan", "start_date") and _has_column("route_plan", "end_date"):
        bind.execute(
            text(
                """
                UPDATE route_plan
                SET
                  start_date = date_trunc('day', start_date),
                  end_date = date_trunc('day', COALESCE(end_date, start_date)) + interval '1 day' - interval '1 microsecond'
                WHERE start_date IS NOT NULL
                """
            )
        )

    if _has_table("route_plan"):
        bind.execute(text("ALTER INDEX IF EXISTS ix_delivery_plan_created_at_id_desc RENAME TO ix_route_plan_created_at_id_desc"))

    if _has_table("local_delivery_plan") and not _has_table("route_group"):
        op.rename_table("local_delivery_plan", "route_group")

    if _has_table("route_group") and _has_column("route_group", "delivery_plan_id"):
        op.alter_column("route_group", "delivery_plan_id", new_column_name="route_plan_id")

    if _has_table("route_group") and not _has_column("route_group", "state_id"):
        op.add_column("route_group", sa.Column("state_id", sa.Integer(), nullable=True))
        op.create_foreign_key(None, "route_group", "plan_state", ["state_id"], ["id"], ondelete="SET NULL")

    for col, col_type in (
        ("total_weight_g", sa.Float()),
        ("total_volume_cm3", sa.Float()),
        ("total_item_count", sa.Integer()),
        ("total_orders", sa.Integer()),
    ):
        if _has_table("route_group") and not _has_column("route_group", col):
            op.add_column("route_group", sa.Column(col, col_type, nullable=True))

    if _has_table("route_solution") and _has_column("route_solution", "local_delivery_plan_id"):
        op.alter_column("route_solution", "local_delivery_plan_id", new_column_name="route_group_id")

    if _has_table("order") and _has_column("order", "delivery_plan_id"):
        op.alter_column("order", "delivery_plan_id", new_column_name="route_plan_id")

    if _has_table("international_shipping_plan") and _has_column("international_shipping_plan", "delivery_plan_id"):
        op.alter_column("international_shipping_plan", "delivery_plan_id", new_column_name="route_plan_id")

    if _has_table("store_pickup_plan") and _has_column("store_pickup_plan", "delivery_plan_id"):
        op.alter_column("store_pickup_plan", "delivery_plan_id", new_column_name="route_plan_id")

    if _has_table("plan_event") and not _has_table("route_plan_event"):
        op.rename_table("plan_event", "route_plan_event")

    if _has_table("route_plan_event") and _has_column("route_plan_event", "delivery_plan_id"):
        op.alter_column("route_plan_event", "delivery_plan_id", new_column_name="route_plan_id")

    if _has_table("plan_event_action") and not _has_table("route_plan_event_action"):
        op.rename_table("plan_event_action", "route_plan_event_action")


def downgrade() -> None:
    bind = op.get_bind()

    if _has_table("route_plan_event_action") and not _has_table("plan_event_action"):
        op.rename_table("route_plan_event_action", "plan_event_action")

    if _has_table("route_plan_event") and _has_column("route_plan_event", "route_plan_id"):
        op.alter_column("route_plan_event", "route_plan_id", new_column_name="delivery_plan_id")

    if _has_table("route_plan_event") and not _has_table("plan_event"):
        op.rename_table("route_plan_event", "plan_event")

    if _has_table("store_pickup_plan") and _has_column("store_pickup_plan", "route_plan_id"):
        op.alter_column("store_pickup_plan", "route_plan_id", new_column_name="delivery_plan_id")

    if _has_table("international_shipping_plan") and _has_column("international_shipping_plan", "route_plan_id"):
        op.alter_column("international_shipping_plan", "route_plan_id", new_column_name="delivery_plan_id")

    if _has_table("order") and _has_column("order", "route_plan_id"):
        op.alter_column("order", "route_plan_id", new_column_name="delivery_plan_id")

    if _has_table("route_solution") and _has_column("route_solution", "route_group_id"):
        op.alter_column("route_solution", "route_group_id", new_column_name="local_delivery_plan_id")

    for col in ("total_orders", "total_item_count", "total_volume_cm3", "total_weight_g"):
        if _has_table("route_group") and _has_column("route_group", col):
            op.drop_column("route_group", col)

    if _has_table("route_group") and _has_column("route_group", "state_id"):
        op.drop_column("route_group", "state_id")

    if _has_table("route_group") and _has_column("route_group", "route_plan_id"):
        op.alter_column("route_group", "route_plan_id", new_column_name="delivery_plan_id")

    if _has_table("route_group") and not _has_table("local_delivery_plan"):
        op.rename_table("route_group", "local_delivery_plan")

    if _has_table("route_plan") and _has_column("route_plan", "date_strategy"):
        op.drop_column("route_plan", "date_strategy")

    if _has_table("route_plan") and not _has_column("route_plan", "plan_type"):
        op.add_column("route_plan", sa.Column("plan_type", sa.String(), nullable=True))
        bind.execute(text("UPDATE route_plan SET plan_type = 'local_delivery' WHERE plan_type IS NULL"))
        op.alter_column("route_plan", "plan_type", nullable=False)

    if _has_table("route_plan"):
        bind.execute(text("ALTER INDEX IF EXISTS ix_route_plan_created_at_id_desc RENAME TO ix_delivery_plan_created_at_id_desc"))

    if _has_table("route_plan") and not _has_table("delivery_plan"):
        op.rename_table("route_plan", "delivery_plan")
