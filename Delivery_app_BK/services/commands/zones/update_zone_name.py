"""Update mutable zone presentation fields on both active and inactive versions."""
from __future__ import annotations

from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.models import Zone, db
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.zones.serialize_zone import serialize_zone


def update_zone_name(ctx: ServiceContext) -> dict:
    zone_id = ctx.incoming_data.get("zone_id")
    version_id = ctx.incoming_data.get("version_id")

    if not zone_id:
        raise ValidationFailed("zone_id is required")

    zone = db.session.get(Zone, zone_id)
    if zone is None or zone.team_id != ctx.team_id:
        raise NotFound(f"Zone {zone_id} not found")

    if version_id is not None and zone.zone_version_id != version_id:
        raise NotFound(f"Zone {zone_id} not found")

    name = ctx.incoming_data.get("name")
    if name is None or not isinstance(name, str) or not name.strip():
        raise ValidationFailed("name must be a non-empty string")

    zone.name = name.strip()
    if "zone_color" in ctx.incoming_data:
        zone.zone_color = ctx.incoming_data.get("zone_color")
    db.session.commit()
    return serialize_zone(zone)
