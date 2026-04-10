"""Refactor vehicle table to canonical schema.

Revision ID: t8u4v0w6x2y9
Revises: s7t3u9v5w1x8
Create Date: 2025-01-03 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "t8u4v0w6x2y9"
down_revision = "s7t3u9v5w1x8"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade():
    # 1. Add registration_number (nullable initially so existing rows can be populated)
    if not _has_column("vehicle", "registration_number"):
        op.add_column(
            "vehicle",
            sa.Column("registration_number", sa.String(), nullable=True),
        )

    # 2. Back-fill from name
    op.execute(
        "UPDATE vehicle SET registration_number = name WHERE registration_number IS NULL"
    )

    # 3. Tighten to NOT NULL now that all rows have a value
    op.alter_column("vehicle", "registration_number", nullable=False)

    # 4. Unique constraint on (team_id, registration_number)
    try:
        op.create_unique_constraint(
            "uq_vehicle_team_registration",
            "vehicle",
            ["team_id", "registration_number"],
        )
    except Exception:
        pass  # already exists — idempotent

    # 5. Rename name → label (keep nullable)
    if _has_column("vehicle", "name"):
        op.alter_column("vehicle", "name", new_column_name="label")
        op.alter_column("vehicle", "label", nullable=True)

    # 6. Rename cost_per_kilometer → cost_per_km
    if _has_column("vehicle", "cost_per_kilometer"):
        op.alter_column("vehicle", "cost_per_kilometer", new_column_name="cost_per_km")

    # 7. Rename travel_duration_limit → travel_duration_limit_minutes
    if _has_column("vehicle", "travel_duration_limit"):
        op.alter_column(
            "vehicle", "travel_duration_limit", new_column_name="travel_duration_limit_minutes"
        )

    # 8. Rename route_distance_limit → travel_distance_limit_km
    if _has_column("vehicle", "route_distance_limit"):
        op.alter_column(
            "vehicle", "route_distance_limit", new_column_name="travel_distance_limit_km"
        )

    # 9. Rename max_load → max_weight_load_g
    if _has_column("vehicle", "max_load"):
        op.alter_column("vehicle", "max_load", new_column_name="max_weight_load_g")

    # 10. Add new capability columns
    if not _has_column("vehicle", "max_volume_load_cm3"):
        op.add_column(
            "vehicle",
            sa.Column("max_volume_load_cm3", sa.Integer(), nullable=True),
        )

    if not _has_column("vehicle", "max_speed_kmh"):
        op.add_column(
            "vehicle",
            sa.Column("max_speed_kmh", sa.Float(), nullable=True),
        )

    if not _has_column("vehicle", "fuel_type"):
        op.add_column(
            "vehicle",
            sa.Column("fuel_type", sa.String(), nullable=True),
        )

    # 11. Change travel_mode from JSONB to String
    #     Use #>> '{}' to extract scalar text value without JSON quotes.
    if _has_column("vehicle", "travel_mode"):
        op.alter_column(
            "vehicle",
            "travel_mode",
            type_=sa.String(),
            postgresql_using="travel_mode #>> '{}'",
        )

    # 12. Drop icon
    if _has_column("vehicle", "icon"):
        op.drop_column("vehicle", "icon")

    # 13. Drop user_id (and its FK constraint)
    if _has_column("vehicle", "user_id"):
        for constraint_name in ("vehicle_user_id_fkey", "fk_vehicle_user_id"):
            try:
                op.drop_constraint(constraint_name, "vehicle", type_="foreignkey")
                break
            except Exception:
                pass
        op.drop_column("vehicle", "user_id")

    # 14. Drop min_load
    if _has_column("vehicle", "min_load"):
        op.drop_column("vehicle", "min_load")


def downgrade():
    # Best-effort reversal — restore dropped columns and reverse renames.

    # Re-add min_load
    if not _has_column("vehicle", "min_load"):
        op.add_column(
            "vehicle",
            sa.Column("min_load", sa.Integer(), nullable=True),
        )

    # Re-add user_id
    if not _has_column("vehicle", "user_id"):
        op.add_column(
            "vehicle",
            sa.Column("user_id", sa.Integer(), nullable=True),
        )

    # Re-add icon
    if not _has_column("vehicle", "icon"):
        op.add_column(
            "vehicle",
            sa.Column("icon", sa.String(), nullable=True),
        )

    # Reverse travel_mode type change (String → JSONB)
    if _has_column("vehicle", "travel_mode"):
        op.alter_column(
            "vehicle",
            "travel_mode",
            type_=sa.Text(),
        )

    # Drop added columns
    if _has_column("vehicle", "fuel_type"):
        op.drop_column("vehicle", "fuel_type")
    if _has_column("vehicle", "max_speed_kmh"):
        op.drop_column("vehicle", "max_speed_kmh")
    if _has_column("vehicle", "max_volume_load_cm3"):
        op.drop_column("vehicle", "max_volume_load_cm3")

    # Reverse renames
    if _has_column("vehicle", "max_weight_load_g"):
        op.alter_column("vehicle", "max_weight_load_g", new_column_name="max_load")
    if _has_column("vehicle", "travel_distance_limit_km"):
        op.alter_column(
            "vehicle", "travel_distance_limit_km", new_column_name="route_distance_limit"
        )
    if _has_column("vehicle", "travel_duration_limit_minutes"):
        op.alter_column(
            "vehicle", "travel_duration_limit_minutes", new_column_name="travel_duration_limit"
        )
    if _has_column("vehicle", "cost_per_km"):
        op.alter_column("vehicle", "cost_per_km", new_column_name="cost_per_kilometer")
    if _has_column("vehicle", "label"):
        op.alter_column("vehicle", "label", new_column_name="name")
        op.alter_column("vehicle", "name", nullable=False)

    # Drop unique constraint
    try:
        op.drop_constraint("uq_vehicle_team_registration", "vehicle", type_="unique")
    except Exception:
        pass

    # Drop registration_number
    if _has_column("vehicle", "registration_number"):
        op.drop_column("vehicle", "registration_number")
