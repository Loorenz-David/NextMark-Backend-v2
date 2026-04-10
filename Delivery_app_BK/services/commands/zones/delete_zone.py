"""Delete a zone from an inactive version."""
from __future__ import annotations

from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.models import RouteGroup, Zone, ZoneVersion, db
from Delivery_app_BK.services.context import ServiceContext


def delete_zone(ctx: ServiceContext) -> dict:
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
        raise ValidationFailed("Cannot delete zones from an active version.")

    route_group_count = RouteGroup.query.filter_by(zone_id=zone.id).count()
    if route_group_count > 0:
        raise ValidationFailed(
            "Route groups derived from this zone exist. Remove them before deleting the zone."
        )

    db.session.delete(zone)
    db.session.commit()

    return {
        "deleted": True,
        "zone_id": zone_id,
    }
