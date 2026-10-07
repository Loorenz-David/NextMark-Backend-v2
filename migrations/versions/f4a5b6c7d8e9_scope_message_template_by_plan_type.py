"""scope message_template by plan_type

A team now owns one template per (event, channel, plan_type) instead of per
(event, channel), so pickup, delivery and shipping customers can receive
different wording, or no message at all, for the same business event.

Existing rows become local_delivery and are cloned into store_pickup and
international_shipping, so every order keeps receiving exactly what it did
before the upgrade until the team edits or disables a copy.

DOWNGRADE IS DESTRUCTIVE: it deletes every non-local_delivery row, including
any edits made to the clones after the upgrade.

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-10-07 00:00:00.000000
"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "f4a5b6c7d8e9"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


TABLE = "message_template"
OLD_UQ = "uq_message_template_team_event_channel"
NEW_UQ = "uq_message_template_team_event_channel_plan_type"
PLAN_TYPE_INDEX = "ix_message_template_plan_type"
SOURCE_PLAN_TYPE = "local_delivery"
CLONE_PLAN_TYPES = ("store_pickup", "international_shipping")


def _has_column(table: str, column: str) -> bool:
    inspector = inspect(op.get_bind())
    return any(c["name"] == column for c in inspector.get_columns(table))


def _has_index(table: str, index: str) -> bool:
    inspector = inspect(op.get_bind())
    return any(i["name"] == index for i in inspector.get_indexes(table))


def _has_unique_constraint(table: str, constraint_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return any(c.get("name") == constraint_name for c in inspector.get_unique_constraints(table))


def _clone_local_delivery_templates() -> None:
    """
    One INSERT ... SELECT per (source row, target plan type). Copying inside
    the database keeps the JSONB columns untouched, and the NOT EXISTS guard
    makes a re-run a no-op.
    """
    bind = op.get_bind()
    source_ids = [
        row[0]
        for row in bind.execute(
            sa.text(f"SELECT id FROM {TABLE} WHERE plan_type = :plan_type ORDER BY id"),
            {"plan_type": SOURCE_PLAN_TYPE},
        ).fetchall()
    ]

    insert_clone = sa.text(
        f"""
        INSERT INTO {TABLE} (
            client_id, event, enable, subject, template, name, ask_permission,
            channel, plan_type, schedule_offset_value, schedule_offset_unit,
            timestampt, team_id
        )
        SELECT
            :client_id, src.event, src.enable, src.subject, src.template, src.name,
            src.ask_permission, src.channel, :plan_type, src.schedule_offset_value,
            src.schedule_offset_unit, src.timestampt, src.team_id
        FROM {TABLE} src
        WHERE src.id = :source_id
          AND NOT EXISTS (
              SELECT 1 FROM {TABLE} dup
              WHERE dup.team_id IS NOT DISTINCT FROM src.team_id
                AND dup.event IS NOT DISTINCT FROM src.event
                AND dup.channel = src.channel
                AND dup.plan_type = :plan_type
          )
        """
    )

    for source_id in source_ids:
        for plan_type in CLONE_PLAN_TYPES:
            bind.execute(
                insert_clone,
                {
                    # Same shape create_instance produces for new rows.
                    "client_id": f"message_template_{uuid4().hex}",
                    "plan_type": plan_type,
                    "source_id": source_id,
                },
            )


def upgrade() -> None:
    if not _has_column(TABLE, "plan_type"):
        with op.batch_alter_table(TABLE, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "plan_type",
                    sa.String(),
                    nullable=False,
                    server_default=SOURCE_PLAN_TYPE,
                )
            )

    if not _has_index(TABLE, PLAN_TYPE_INDEX):
        with op.batch_alter_table(TABLE, schema=None) as batch_op:
            batch_op.create_index(batch_op.f(PLAN_TYPE_INDEX), ["plan_type"], unique=False)

    if _has_unique_constraint(TABLE, OLD_UQ):
        with op.batch_alter_table(TABLE, schema=None) as batch_op:
            batch_op.drop_constraint(OLD_UQ, type_="unique")

    if not _has_unique_constraint(TABLE, NEW_UQ):
        with op.batch_alter_table(TABLE, schema=None) as batch_op:
            batch_op.create_unique_constraint(NEW_UQ, ["team_id", "event", "channel", "plan_type"])

    _clone_local_delivery_templates()

    # Existing rows are backfilled by the server default above. Drop it so new
    # rows cannot silently inherit a plan type they never declared.
    with op.batch_alter_table(TABLE, schema=None) as batch_op:
        batch_op.alter_column("plan_type", server_default=None)


def downgrade() -> None:
    if _has_column(TABLE, "plan_type"):
        op.execute(
            sa.text(f"DELETE FROM {TABLE} WHERE plan_type <> :plan_type").bindparams(
                plan_type=SOURCE_PLAN_TYPE
            )
        )

    if _has_unique_constraint(TABLE, NEW_UQ):
        with op.batch_alter_table(TABLE, schema=None) as batch_op:
            batch_op.drop_constraint(NEW_UQ, type_="unique")

    if not _has_unique_constraint(TABLE, OLD_UQ):
        with op.batch_alter_table(TABLE, schema=None) as batch_op:
            batch_op.create_unique_constraint(OLD_UQ, ["team_id", "event", "channel"])

    if _has_index(TABLE, PLAN_TYPE_INDEX):
        with op.batch_alter_table(TABLE, schema=None) as batch_op:
            batch_op.drop_index(batch_op.f(PLAN_TYPE_INDEX))

    if _has_column(TABLE, "plan_type"):
        with op.batch_alter_table(TABLE, schema=None) as batch_op:
            batch_op.drop_column("plan_type")
