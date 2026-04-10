"""PostGIS helpers for deriving zone geometry artifacts."""
from __future__ import annotations

from sqlalchemy import text

from Delivery_app_BK.models import db


DEFAULT_SIMPLIFY_TOLERANCE = 0.0001


def is_postgresql_backend() -> bool:
    bind = db.session.get_bind()
    if bind is None:
        return False
    return bind.dialect.name == "postgresql"


def refresh_zone_geometry_derivatives(
    zone_id: int,
    *,
    simplify_tolerance: float = DEFAULT_SIMPLIFY_TOLERANCE,
) -> None:
    """Recompute simplified geometry, centroid and bbox from high-res geometry."""
    if not is_postgresql_backend():
        return

    db.session.execute(
        text(
            """
            UPDATE zone
            SET
                geom_simplified = ST_SimplifyPreserveTopology(geom_high_res, :tol),
                centroid_lat = ST_Y(ST_Centroid(geom_high_res)),
                centroid_lng = ST_X(ST_Centroid(geom_high_res)),
                min_lat = ST_YMin(geom_high_res),
                max_lat = ST_YMax(geom_high_res),
                min_lng = ST_XMin(geom_high_res),
                max_lng = ST_XMax(geom_high_res)
            WHERE id = :zone_id
              AND geom_high_res IS NOT NULL
            """
        ),
        {
            "zone_id": zone_id,
            "tol": simplify_tolerance,
        },
    )
