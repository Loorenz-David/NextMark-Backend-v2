"""add order_schedule_targets table

Revision ID: s4t8u2v6w1x9
Revises: p8q2r5s9t1u7
Create Date: 2026-04-22 09:45:00.000000

"""

from alembic import op
import sqlalchemy as sa

from Delivery_app_BK.models.utils import UTCDateTime


# revision identifiers, used by Alembic.
revision = "s4t8u2v6w1x9"
down_revision = "p8q2r5s9t1u7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_schedule_targets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("endpoint_url", sa.String(), nullable=False),
        sa.Column("api_key", sa.String(), nullable=False),
        sa.Column("external_shop_id", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_order_schedule_targets_client_id"),
        "order_schedule_targets",
        ["client_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_order_schedule_targets_team_id"),
        "order_schedule_targets",
        ["team_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_order_schedule_targets_team_id"), table_name="order_schedule_targets")
    op.drop_index(op.f("ix_order_schedule_targets_client_id"), table_name="order_schedule_targets")
    op.drop_table("order_schedule_targets")
