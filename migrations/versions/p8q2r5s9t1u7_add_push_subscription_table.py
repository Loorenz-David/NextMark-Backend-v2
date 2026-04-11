"""add push_subscription table

Revision ID: p8q2r5s9t1u7
Revises: m2p7q1w8x4y6
Create Date: 2026-04-11 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

from Delivery_app_BK.models.utils import UTCDateTime

revision = "p8q2r5s9t1u7"
down_revision = "m2p7q1w8x4y6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "push_subscription",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.Text(), nullable=False),
        sa.Column("auth", sa.Text(), nullable=False),
        sa.Column("expiration_time", sa.Text(), nullable=True),
        sa.Column("subscription_json", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_seen_at", UTCDateTime(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint"),
    )
    op.create_index("ix_push_subscription_user_id", "push_subscription", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_push_subscription_user_id", table_name="push_subscription")
    op.drop_table("push_subscription")
