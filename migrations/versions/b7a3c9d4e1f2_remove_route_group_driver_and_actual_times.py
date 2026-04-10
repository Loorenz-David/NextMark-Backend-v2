"""remove_route_group_driver_and_actual_times

Revision ID: b7a3c9d4e1f2
Revises: e3f9a1c6b2d4
Create Date: 2026-03-28 14:20:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b7a3c9d4e1f2"
down_revision = "e3f9a1c6b2d4"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


def _find_fk_name(table_name: str, constrained_column: str, referred_table: str) -> str | None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys(table_name):
        constrained = fk.get("constrained_columns") or []
        if constrained_column in constrained and fk.get("referred_table") == referred_table:
            return fk.get("name")
    return None


def upgrade():
    fk_name = _find_fk_name("route_group", "driver_id", "user")

    with op.batch_alter_table("route_group", schema=None) as batch_op:
        if fk_name:
            batch_op.drop_constraint(fk_name, type_="foreignkey")
        if _has_column("route_group", "driver_id"):
            batch_op.drop_column("driver_id")
        if _has_column("route_group", "actual_start_time"):
            batch_op.drop_column("actual_start_time")
        if _has_column("route_group", "actual_end_time"):
            batch_op.drop_column("actual_end_time")


def downgrade():
    with op.batch_alter_table("route_group", schema=None) as batch_op:
        if not _has_column("route_group", "actual_start_time"):
            batch_op.add_column(sa.Column("actual_start_time", sa.DateTime(timezone=True), nullable=True))
        if not _has_column("route_group", "actual_end_time"):
            batch_op.add_column(sa.Column("actual_end_time", sa.DateTime(timezone=True), nullable=True))
        if not _has_column("route_group", "driver_id"):
            batch_op.add_column(sa.Column("driver_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_route_group_driver_id_user",
                "user",
                ["driver_id"],
                ["id"],
            )
