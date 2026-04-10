"""Update geometry for a zone - only allowed on zones in an inactive version."""
from __future__ import annotations

from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.models import Zone, ZoneVersion, db
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.zones.serialize_zone import serialize_zone
from Delivery_app_BK.zones.services.postgis_geometry import refresh_zone_geometry_derivatives


_GEOMETRY_FIELDS = {
    "geometry",
    "centroid_lat",
    "centroid_lng",
    "min_lat",
    "max_lat",
    "min_lng",
    "max_lng",
}


def update_zone_geometry(ctx: ServiceContext) -> dict:
    zone_id = ctx.incoming_data.get("zone_id")
    version_id = ctx.incoming_data.get("version_id")

    if not zone_id:
        raise ValidationFailed("zone_id is required")

    zone = db.session.get(Zone, zone_id)
    if zone is None or zone.team_id != ctx.team_id:
        raise NotFound(f"Zone {zone_id} not found")

    if version_id is not None and zone.zone_version_id != version_id:
        raise NotFound(f"Zone {zone_id} not found")

    version = db.session.get(ZoneVersion, zone.zone_version_id)
    if version is None or version.team_id != ctx.team_id:
        raise NotFound(f"Zone version for zone {zone_id} not found")

    if version.is_active:
        raise ValidationFailed(
            "Cannot edit zone geometry in an active version. Create a new version to redraw zone boundaries."
        )

    geometry_updated = False
    fields_found = False

    for field in _GEOMETRY_FIELDS:
        if field not in ctx.incoming_data:
            continue
        fields_found = True
        value = ctx.incoming_data.get(field)
        if field == "geometry":
            geometry_updated = True
        setattr(zone, field, value)

    if not fields_found:
        raise ValidationFailed("No geometry fields provided.")

    if geometry_updated:
        db.session.flush()
        refresh_zone_geometry_derivatives(zone.id)

    db.session.commit()
    return serialize_zone(zone)
