"""Create a new Zone record within a ZoneVersion."""
from __future__ import annotations

from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.models import db
from Delivery_app_BK.models.tables.zones.zone import Zone
from Delivery_app_BK.models.tables.zones.zone_version import ZoneVersion
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.zones.serialize_zone import serialize_zone
from Delivery_app_BK.zones.services.postgis_geometry import refresh_zone_geometry_derivatives

_VALID_ZONE_TYPES = frozenset({"bootstrap", "system", "user"})


def create_zone(ctx: ServiceContext) -> dict:
    """Create a new Zone record under the specified zone version."""
    version_id = ctx.incoming_data.get("version_id")
    name = ctx.incoming_data.get("name")
    zone_color = ctx.incoming_data.get("zone_color")
    zone_type = ctx.incoming_data.get("zone_type", "user")

    if not version_id:
        raise ValidationFailed("version_id is required")
    if not name:
        raise ValidationFailed("name is required")
    if zone_type not in _VALID_ZONE_TYPES:
        raise ValidationFailed(f"zone_type must be one of {sorted(_VALID_ZONE_TYPES)}")

    version = db.session.get(ZoneVersion, version_id)
    if version is None or version.team_id != ctx.team_id:
        raise NotFound(f"Zone version {version_id} not found")

    zone = Zone(
        team_id=ctx.team_id,
        zone_version_id=version_id,
        city_key=version.city_key,
        name=name,
        zone_color=zone_color,
        zone_type=zone_type,
        centroid_lat=ctx.incoming_data.get("centroid_lat"),
        centroid_lng=ctx.incoming_data.get("centroid_lng"),
        geometry=ctx.incoming_data.get("geometry"),
        min_lat=ctx.incoming_data.get("min_lat"),
        max_lat=ctx.incoming_data.get("max_lat"),
        min_lng=ctx.incoming_data.get("min_lng"),
        max_lng=ctx.incoming_data.get("max_lng"),
        is_active=True,
    )
    db.session.add(zone)
    db.session.flush()
    refresh_zone_geometry_derivatives(zone.id)
    db.session.commit()
    return serialize_zone(zone)
