"""add trusted_device tables

Revision ID: tdv1a2b3c4d5
Revises: 2ac9630b7928
Create Date: 2026-07-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from Delivery_app_BK.models.utils import UTCDateTime

revision = "tdv1a2b3c4d5"
down_revision = "2ac9630b7928"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trusted_device",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("device_secret_hash", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_used_at", UTCDateTime(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.Column("registered_by_user_id", sa.Integer(), nullable=True),
        sa.Column("revoked_at", UTCDateTime(), nullable=True),
        sa.Column("revoked_by_user_id", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["registered_by_user_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["revoked_by_user_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_trusted_device_client_id"), "trusted_device", ["client_id"])
    op.create_index(op.f("ix_trusted_device_is_active"), "trusted_device", ["is_active"])

    op.create_table(
        "trusted_device_user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trusted_device_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("revoked_at", UTCDateTime(), nullable=True),
        sa.Column("revoked_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["trusted_device_id"], ["trusted_device.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["revoked_by_user_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "trusted_device_id",
            "user_id",
            name="uq_trusted_device_user_device_user",
        ),
    )
    op.create_index(
        op.f("ix_trusted_device_user_trusted_device_id"),
        "trusted_device_user",
        ["trusted_device_id"],
    )
    op.create_index(
        op.f("ix_trusted_device_user_user_id"),
        "trusted_device_user",
        ["user_id"],
    )
    op.create_index(
        op.f("ix_trusted_device_user_is_active"),
        "trusted_device_user",
        ["is_active"],
    )

    op.create_table(
        "trusted_device_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_name", sa.String(), nullable=False),
        sa.Column("result", sa.String(), nullable=False),
        sa.Column("trusted_device_id", sa.Integer(), nullable=True),
        sa.Column("initiating_user_id", sa.Integer(), nullable=True),
        sa.Column("target_user_id", sa.Integer(), nullable=True),
        sa.Column("request_ip", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("detail", JSONB().with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["trusted_device_id"], ["trusted_device.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["initiating_user_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_user_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_trusted_device_event_event_name"),
        "trusted_device_event",
        ["event_name"],
    )
    op.create_index(
        op.f("ix_trusted_device_event_trusted_device_id"),
        "trusted_device_event",
        ["trusted_device_id"],
    )
    op.create_index(
        op.f("ix_trusted_device_event_created_at"),
        "trusted_device_event",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_trusted_device_event_created_at"), table_name="trusted_device_event")
    op.drop_index(op.f("ix_trusted_device_event_trusted_device_id"), table_name="trusted_device_event")
    op.drop_index(op.f("ix_trusted_device_event_event_name"), table_name="trusted_device_event")
    op.drop_table("trusted_device_event")

    op.drop_index(op.f("ix_trusted_device_user_is_active"), table_name="trusted_device_user")
    op.drop_index(op.f("ix_trusted_device_user_user_id"), table_name="trusted_device_user")
    op.drop_index(op.f("ix_trusted_device_user_trusted_device_id"), table_name="trusted_device_user")
    op.drop_table("trusted_device_user")

    op.drop_index(op.f("ix_trusted_device_is_active"), table_name="trusted_device")
    op.drop_index(op.f("ix_trusted_device_client_id"), table_name="trusted_device")
    op.drop_table("trusted_device")
