"""order delivery window strict interval safeguards

Revision ID: b2e4d9f6c1aa
Revises: 7f66a23de2a6
Create Date: 2026-03-03 19:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b2e4d9f6c1aa"
down_revision = "7f66a23de2a6"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = {index["name"] for index in inspector.get_indexes("order_delivery_window")}
    existing_checks = {check["name"] for check in inspector.get_check_constraints("order_delivery_window")}

    with op.batch_alter_table("order_delivery_window", schema=None) as batch_op:
        if "ix_order_delivery_window_order_id_start_at" not in existing_indexes:
            batch_op.create_index(
                "ix_order_delivery_window_order_id_start_at",
                ["order_id", "start_at"],
                unique=False,
            )
        if "ck_order_delivery_window_end_after_start" not in existing_checks:
            batch_op.create_check_constraint(
                "ck_order_delivery_window_end_after_start",
                "end_at > start_at",
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = {index["name"] for index in inspector.get_indexes("order_delivery_window")}
    existing_checks = {check["name"] for check in inspector.get_check_constraints("order_delivery_window")}

    with op.batch_alter_table("order_delivery_window", schema=None) as batch_op:
        if "ck_order_delivery_window_end_after_start" in existing_checks:
            batch_op.drop_constraint("ck_order_delivery_window_end_after_start", type_="check")
        if "ix_order_delivery_window_order_id_start_at" in existing_indexes:
            batch_op.drop_index("ix_order_delivery_window_order_id_start_at")
