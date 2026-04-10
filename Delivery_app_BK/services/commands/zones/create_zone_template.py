"""Create or replace the active template for a zone."""
from __future__ import annotations

from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.models import Facility, Zone, ZoneTemplate, db
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.zones.serialize_zone_template import (
    serialize_zone_template,
)
from Delivery_app_BK.services.requests.zones.zone_template import (
    parse_zone_template_request,
)


def create_zone_template(ctx: ServiceContext) -> dict:
    """Upsert the active template for a zone by creating a new template version."""
    zone_id = ctx.incoming_data.get("zone_id")
    version_id = ctx.incoming_data.get("version_id")

    if not zone_id:
        raise ValidationFailed("zone_id is required")

    request_payload = {
        key: value
        for key, value in (ctx.incoming_data or {}).items()
        if key not in {"zone_id", "version_id"}
    }
    req = parse_zone_template_request(request_payload)

    zone = db.session.get(Zone, zone_id)
    if zone is None or zone.team_id != ctx.team_id:
        raise NotFound(f"Zone {zone_id} not found")
    if version_id is not None and zone.zone_version_id != version_id:
        raise ValidationFailed(f"Zone {zone_id} does not belong to version {version_id}")

    if req.default_facility_id is not None:
        facility = db.session.get(Facility, req.default_facility_id)
        if facility is None or facility.team_id != ctx.team_id:
            raise NotFound(f"Facility {req.default_facility_id} not found")

    current_active = ZoneTemplate.query.filter_by(
        team_id=ctx.team_id,
        zone_id=zone_id,
        is_active=True,
    ).all()
    for template in current_active:
        template.is_active = False

    latest = (
        ZoneTemplate.query.filter_by(team_id=ctx.team_id, zone_id=zone_id)
        .order_by(ZoneTemplate.version.desc())
        .first()
    )
    next_version = (latest.version + 1) if latest else 1

    created = ZoneTemplate(
        team_id=ctx.team_id,
        zone_id=zone_id,
        name=req.name,
        version=next_version,
        is_active=True,
        default_facility_id=req.default_facility_id,
        max_orders_per_route=req.max_orders_per_route,
        max_vehicles=req.max_vehicles,
        operating_window_start=req.operating_window_start,
        operating_window_end=req.operating_window_end,
        eta_tolerance_seconds=req.eta_tolerance_seconds,
        vehicle_capabilities_required=req.vehicle_capabilities_required,
        preferred_vehicle_ids=req.preferred_vehicle_ids,
        default_route_end_strategy=req.default_route_end_strategy,
        meta=req.meta,
    )
    db.session.add(created)
    db.session.commit()

    return serialize_zone_template(created)
