"""Add scope and payload to order event action."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "u6v2w8x4y1z7"
down_revision = "t4u8v2w6x1y5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "order_event_action",
        sa.Column("action_scope", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "order_event_action",
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
    )
    op.create_index(
        op.f("ix_order_event_action_action_scope"),
        "order_event_action",
        ["action_scope"],
        unique=False,
    )
    op.drop_constraint(
        "uq_order_event_action_event_name",
        "order_event_action",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_order_event_action_event_scope",
        "order_event_action",
        ["event_id", "action_name", "action_scope"],
    )


def downgrade():
    op.drop_constraint(
        "uq_order_event_action_event_scope",
        "order_event_action",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_order_event_action_event_name",
        "order_event_action",
        ["event_id", "action_name"],
    )
    op.drop_index(
        op.f("ix_order_event_action_action_scope"),
        table_name="order_event_action",
    )
    op.drop_column("order_event_action", "payload")
    op.drop_column("order_event_action", "action_scope")
