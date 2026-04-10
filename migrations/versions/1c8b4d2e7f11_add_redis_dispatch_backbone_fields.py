"""add redis dispatch backbone fields

Revision ID: 1c8b4d2e7f11
Revises: 0f2d8b6e4c91
Create Date: 2026-03-14 19:10:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "1c8b4d2e7f11"
down_revision = "0f2d8b6e4c91"
branch_labels = None
depends_on = None


def _add_dispatch_columns(table_name: str) -> None:
    op.add_column(table_name, sa.Column("event_id", sa.String(), nullable=True))
    op.add_column(table_name, sa.Column("entity_type", sa.String(), nullable=True))
    op.add_column(table_name, sa.Column("entity_id", sa.String(), nullable=True))
    op.add_column(table_name, sa.Column("entity_version", sa.String(), nullable=True))
    op.add_column(
        table_name,
        sa.Column("dispatch_status", sa.String(), nullable=False, server_default="PENDING"),
    )
    op.add_column(
        table_name,
        sa.Column("dispatch_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(table_name, sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table_name, sa.Column("claimed_by", sa.String(), nullable=True))
    op.add_column(
        table_name,
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(table_name, sa.Column("last_error", sa.Text(), nullable=True))

    op.create_index(op.f(f"ix_{table_name}_event_id"), table_name, ["event_id"], unique=True)
    op.create_index(op.f(f"ix_{table_name}_entity_type"), table_name, ["entity_type"], unique=False)
    op.create_index(op.f(f"ix_{table_name}_entity_id"), table_name, ["entity_id"], unique=False)
    op.create_index(op.f(f"ix_{table_name}_entity_version"), table_name, ["entity_version"], unique=False)
    op.create_index(op.f(f"ix_{table_name}_dispatch_status"), table_name, ["dispatch_status"], unique=False)
    op.create_index(op.f(f"ix_{table_name}_claimed_at"), table_name, ["claimed_at"], unique=False)
    op.create_index(op.f(f"ix_{table_name}_claimed_by"), table_name, ["claimed_by"], unique=False)
    op.create_index(op.f(f"ix_{table_name}_next_attempt_at"), table_name, ["next_attempt_at"], unique=False)


def _drop_dispatch_columns(table_name: str) -> None:
    op.drop_index(op.f(f"ix_{table_name}_next_attempt_at"), table_name=table_name)
    op.drop_index(op.f(f"ix_{table_name}_claimed_by"), table_name=table_name)
    op.drop_index(op.f(f"ix_{table_name}_claimed_at"), table_name=table_name)
    op.drop_index(op.f(f"ix_{table_name}_dispatch_status"), table_name=table_name)
    op.drop_index(op.f(f"ix_{table_name}_entity_version"), table_name=table_name)
    op.drop_index(op.f(f"ix_{table_name}_entity_id"), table_name=table_name)
    op.drop_index(op.f(f"ix_{table_name}_entity_type"), table_name=table_name)
    op.drop_index(op.f(f"ix_{table_name}_event_id"), table_name=table_name)

    op.drop_column(table_name, "last_error")
    op.drop_column(table_name, "next_attempt_at")
    op.drop_column(table_name, "claimed_by")
    op.drop_column(table_name, "claimed_at")
    op.drop_column(table_name, "dispatch_attempts")
    op.drop_column(table_name, "dispatch_status")
    op.drop_column(table_name, "entity_version")
    op.drop_column(table_name, "entity_id")
    op.drop_column(table_name, "entity_type")
    op.drop_column(table_name, "event_id")


def upgrade():
    _add_dispatch_columns("order_event")
    _add_dispatch_columns("plan_event")

    op.create_table(
        "app_event_outbox",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_name", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("event_id", sa.String(), nullable=True),
        sa.Column("entity_type", sa.String(), nullable=True),
        sa.Column("entity_id", sa.String(), nullable=True),
        sa.Column("entity_version", sa.String(), nullable=True),
        sa.Column("dispatch_status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("dispatch_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_by", sa.String(), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["actor_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_app_event_outbox_event_name"), "app_event_outbox", ["event_name"], unique=False)
    op.create_index(op.f("ix_app_event_outbox_occurred_at"), "app_event_outbox", ["occurred_at"], unique=False)
    op.create_index(op.f("ix_app_event_outbox_event_id"), "app_event_outbox", ["event_id"], unique=True)
    op.create_index(op.f("ix_app_event_outbox_entity_type"), "app_event_outbox", ["entity_type"], unique=False)
    op.create_index(op.f("ix_app_event_outbox_entity_id"), "app_event_outbox", ["entity_id"], unique=False)
    op.create_index(op.f("ix_app_event_outbox_entity_version"), "app_event_outbox", ["entity_version"], unique=False)
    op.create_index(op.f("ix_app_event_outbox_dispatch_status"), "app_event_outbox", ["dispatch_status"], unique=False)
    op.create_index(op.f("ix_app_event_outbox_claimed_at"), "app_event_outbox", ["claimed_at"], unique=False)
    op.create_index(op.f("ix_app_event_outbox_claimed_by"), "app_event_outbox", ["claimed_by"], unique=False)
    op.create_index(op.f("ix_app_event_outbox_next_attempt_at"), "app_event_outbox", ["next_attempt_at"], unique=False)

    op.execute(
        """
        UPDATE order_event
        SET
            event_id = CONCAT('order-event:', id),
            entity_type = 'order',
            entity_id = CAST(order_id AS TEXT),
            dispatch_status = 'PENDING',
            dispatch_attempts = 0,
            next_attempt_at = occurred_at
        WHERE event_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE plan_event
        SET
            event_id = CONCAT('plan-event:', id),
            entity_type = 'delivery_plan',
            entity_id = CAST(delivery_plan_id AS TEXT),
            dispatch_status = 'PENDING',
            dispatch_attempts = 0,
            next_attempt_at = occurred_at
        WHERE event_id IS NULL
        """
    )

    op.alter_column("order_event", "next_attempt_at", nullable=False)
    op.alter_column("plan_event", "next_attempt_at", nullable=False)


def downgrade():
    op.drop_index(op.f("ix_app_event_outbox_next_attempt_at"), table_name="app_event_outbox")
    op.drop_index(op.f("ix_app_event_outbox_claimed_by"), table_name="app_event_outbox")
    op.drop_index(op.f("ix_app_event_outbox_claimed_at"), table_name="app_event_outbox")
    op.drop_index(op.f("ix_app_event_outbox_dispatch_status"), table_name="app_event_outbox")
    op.drop_index(op.f("ix_app_event_outbox_entity_version"), table_name="app_event_outbox")
    op.drop_index(op.f("ix_app_event_outbox_entity_id"), table_name="app_event_outbox")
    op.drop_index(op.f("ix_app_event_outbox_entity_type"), table_name="app_event_outbox")
    op.drop_index(op.f("ix_app_event_outbox_event_id"), table_name="app_event_outbox")
    op.drop_index(op.f("ix_app_event_outbox_occurred_at"), table_name="app_event_outbox")
    op.drop_index(op.f("ix_app_event_outbox_event_name"), table_name="app_event_outbox")
    op.drop_table("app_event_outbox")

    _drop_dispatch_columns("plan_event")
    _drop_dispatch_columns("order_event")
