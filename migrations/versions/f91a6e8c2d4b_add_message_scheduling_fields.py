"""add message scheduling fields

Revision ID: f91a6e8c2d4b
Revises: e4c2b9a17d55
Create Date: 2026-03-14 23:59:50.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f91a6e8c2d4b"
down_revision = "e4c2b9a17d55"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("message_template", sa.Column("schedule_offset_value", sa.Integer(), nullable=True))
    op.add_column("message_template", sa.Column("schedule_offset_unit", sa.String(), nullable=True))

    op.add_column("order_event_action", sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True))
    op.add_column("order_event_action", sa.Column("enqueued_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("order_event_action", sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("order_event_action", sa.Column("schedule_anchor_type", sa.String(), nullable=True))
    op.add_column("order_event_action", sa.Column("schedule_anchor_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_order_event_action_scheduled_for"), "order_event_action", ["scheduled_for"], unique=False)
    op.create_index(op.f("ix_order_event_action_enqueued_at"), "order_event_action", ["enqueued_at"], unique=False)
    op.create_index(op.f("ix_order_event_action_processed_at"), "order_event_action", ["processed_at"], unique=False)
    op.create_index(op.f("ix_order_event_action_schedule_anchor_type"), "order_event_action", ["schedule_anchor_type"], unique=False)

    op.add_column("plan_event_action", sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True))
    op.add_column("plan_event_action", sa.Column("enqueued_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("plan_event_action", sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("plan_event_action", sa.Column("schedule_anchor_type", sa.String(), nullable=True))
    op.add_column("plan_event_action", sa.Column("schedule_anchor_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_plan_event_action_scheduled_for"), "plan_event_action", ["scheduled_for"], unique=False)
    op.create_index(op.f("ix_plan_event_action_enqueued_at"), "plan_event_action", ["enqueued_at"], unique=False)
    op.create_index(op.f("ix_plan_event_action_processed_at"), "plan_event_action", ["processed_at"], unique=False)
    op.create_index(op.f("ix_plan_event_action_schedule_anchor_type"), "plan_event_action", ["schedule_anchor_type"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_plan_event_action_schedule_anchor_type"), table_name="plan_event_action")
    op.drop_index(op.f("ix_plan_event_action_processed_at"), table_name="plan_event_action")
    op.drop_index(op.f("ix_plan_event_action_enqueued_at"), table_name="plan_event_action")
    op.drop_index(op.f("ix_plan_event_action_scheduled_for"), table_name="plan_event_action")
    op.drop_column("plan_event_action", "schedule_anchor_at")
    op.drop_column("plan_event_action", "schedule_anchor_type")
    op.drop_column("plan_event_action", "processed_at")
    op.drop_column("plan_event_action", "enqueued_at")
    op.drop_column("plan_event_action", "scheduled_for")

    op.drop_index(op.f("ix_order_event_action_schedule_anchor_type"), table_name="order_event_action")
    op.drop_index(op.f("ix_order_event_action_processed_at"), table_name="order_event_action")
    op.drop_index(op.f("ix_order_event_action_enqueued_at"), table_name="order_event_action")
    op.drop_index(op.f("ix_order_event_action_scheduled_for"), table_name="order_event_action")
    op.drop_column("order_event_action", "schedule_anchor_at")
    op.drop_column("order_event_action", "schedule_anchor_type")
    op.drop_column("order_event_action", "processed_at")
    op.drop_column("order_event_action", "enqueued_at")
    op.drop_column("order_event_action", "scheduled_for")

    op.drop_column("message_template", "schedule_offset_unit")
    op.drop_column("message_template", "schedule_offset_value")
