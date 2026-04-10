"""migrate zone geometry to postgis columns

Revision ID: a7d3f2c1b9e6
Revises: 1d583fb74800
Create Date: 2026-03-27 19:05:00.000000

"""
from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "a7d3f2c1b9e6"
down_revision = "1d583fb74800"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(col.get("name") == column for col in inspector.get_columns(table))


def _has_index(table: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(ix.get("name") == index_name for ix in inspector.get_indexes(table))


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

        if not _has_column("zone", "geom_high_res"):
            op.add_column(
                "zone",
                sa.Column(
                    "geom_high_res",
                    Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False),
                    nullable=True,
                ),
            )
        if not _has_column("zone", "geom_simplified"):
            op.add_column(
                "zone",
                sa.Column(
                    "geom_simplified",
                    Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False),
                    nullable=True,
                ),
            )

        if not _has_index("zone", "ix_zone_geom_high_res_gist"):
            op.execute("CREATE INDEX ix_zone_geom_high_res_gist ON zone USING GIST (geom_high_res)")
        if not _has_index("zone", "ix_zone_geom_simplified_gist"):
            op.execute("CREATE INDEX ix_zone_geom_simplified_gist ON zone USING GIST (geom_simplified)")

        if _has_column("zone", "geometry"):
            op.execute(
                """
                UPDATE zone
                SET geom_high_res = ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(geometry::text), 4326))
                WHERE geometry IS NOT NULL
                """
            )

            op.execute(
                """
                UPDATE zone
                SET
                    geom_simplified = ST_SimplifyPreserveTopology(geom_high_res, 0.0001),
                    centroid_lat = ST_Y(ST_Centroid(geom_high_res)),
                    centroid_lng = ST_X(ST_Centroid(geom_high_res)),
                    min_lat = ST_YMin(geom_high_res),
                    max_lat = ST_YMax(geom_high_res),
                    min_lng = ST_XMin(geom_high_res),
                    max_lng = ST_XMax(geom_high_res)
                WHERE geom_high_res IS NOT NULL
                """
            )

            op.drop_column("zone", "geometry")

    else:
        if not _has_column("zone", "geom_high_res"):
            op.add_column("zone", sa.Column("geom_high_res", sa.JSON(), nullable=True))
        if not _has_column("zone", "geom_simplified"):
            op.add_column("zone", sa.Column("geom_simplified", sa.JSON(), nullable=True))

        if _has_column("zone", "geometry"):
            op.execute(
                """
                UPDATE zone
                SET
                    geom_high_res = geometry,
                    geom_simplified = geometry
                WHERE geometry IS NOT NULL
                """
            )
            op.drop_column("zone", "geometry")


def downgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        if not _has_column("zone", "geometry"):
            op.add_column(
                "zone",
                sa.Column(
                    "geometry",
                    postgresql.JSONB(astext_type=sa.Text()),
                    nullable=True,
                ),
            )

        if _has_column("zone", "geom_high_res"):
            op.execute(
                """
                UPDATE zone
                SET geometry = ST_AsGeoJSON(geom_high_res)::jsonb
                WHERE geom_high_res IS NOT NULL
                """
            )

        if _has_index("zone", "ix_zone_geom_high_res_gist"):
            op.execute("DROP INDEX IF EXISTS ix_zone_geom_high_res_gist")
        if _has_index("zone", "ix_zone_geom_simplified_gist"):
            op.execute("DROP INDEX IF EXISTS ix_zone_geom_simplified_gist")

        if _has_column("zone", "geom_simplified"):
            op.drop_column("zone", "geom_simplified")
        if _has_column("zone", "geom_high_res"):
            op.drop_column("zone", "geom_high_res")

    else:
        if not _has_column("zone", "geometry"):
            op.add_column("zone", sa.Column("geometry", sa.JSON(), nullable=True))

        if _has_column("zone", "geom_high_res"):
            op.execute(
                """
                UPDATE zone
                SET geometry = geom_high_res
                WHERE geom_high_res IS NOT NULL
                """
            )

        if _has_column("zone", "geom_simplified"):
            op.drop_column("zone", "geom_simplified")
        if _has_column("zone", "geom_high_res"):
            op.drop_column("zone", "geom_high_res")
