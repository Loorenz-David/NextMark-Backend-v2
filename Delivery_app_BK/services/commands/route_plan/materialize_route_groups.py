"""Materialize route groups from selected zones for a route plan."""
from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.models import RouteGroup, RoutePlan, Zone, ZoneTemplate, db
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.route_operations.plan.recompute_route_group_totals import (
    recompute_route_group_totals,
)
from Delivery_app_BK.services.domain.route_operations.plan.route_group_zone_snapshot import (
    build_route_group_zone_snapshot,
)
from Delivery_app_BK.services.queries.route_plan.plan_types.serialize_route_group import (
    serialize_route_group,
)
from Delivery_app_BK.services.commands.route_plan.zone_template_defaults import (
    build_zone_template_snapshot,
)


def _normalize_zone_ids(raw_zone_ids) -> list[int]:
    if not isinstance(raw_zone_ids, list) or not raw_zone_ids:
        raise ValidationFailed("zone_ids must be a non-empty list of integers")

    normalized: list[int] = []
    seen: set[int] = set()
    for index, zone_id in enumerate(raw_zone_ids):
        if isinstance(zone_id, bool) or not isinstance(zone_id, int):
            raise ValidationFailed(f"zone_ids[{index}] must be an integer")
        if zone_id <= 0:
            raise ValidationFailed(f"zone_ids[{index}] must be greater than 0")
        if zone_id in seen:
            continue
        seen.add(zone_id)
        normalized.append(zone_id)
    return normalized


def materialize_route_groups(ctx: ServiceContext) -> list[dict]:
    """Create one route group per selected zone for the provided route plan."""
    route_plan_id = ctx.incoming_data.get("route_plan_id")
    zone_ids = _normalize_zone_ids(ctx.incoming_data.get("zone_ids"))

    if not route_plan_id:
        raise ValidationFailed("route_plan_id is required")

    route_plan = db.session.get(RoutePlan, route_plan_id)
    if route_plan is None or route_plan.team_id != ctx.team_id:
        raise NotFound(f"Route plan {route_plan_id} not found")

    zones = (
        Zone.query.filter(
            Zone.id.in_(zone_ids),
            Zone.team_id == ctx.team_id,
            Zone.is_active.is_(True),
        )
        .order_by(Zone.name.asc())
        .all()
    )
    found_zone_ids = {zone.id for zone in zones}
    missing_zone_ids = [zone_id for zone_id in zone_ids if zone_id not in found_zone_ids]
    if missing_zone_ids:
        raise ValidationFailed(f"Invalid zone_ids for this team: {missing_zone_ids}")

    zone_by_id = {zone.id: zone for zone in zones}
    ordered_zones = [zone_by_id[zone_id] for zone_id in zone_ids]

    created_or_existing: list[RouteGroup] = []
    for zone in ordered_zones:
        existing = RouteGroup.query.filter_by(
            route_plan_id=route_plan_id,
            zone_id=zone.id,
            team_id=ctx.team_id,
        ).first()
        if existing is not None:
            created_or_existing.append(existing)
            continue

        active_template = ZoneTemplate.query.filter_by(
            team_id=ctx.team_id,
            zone_id=zone.id,
            is_active=True,
        ).first()

        route_group = RouteGroup(
            team_id=ctx.team_id,
            client_id=f"route_group:{route_plan_id}:{zone.id}",
            route_plan_id=route_plan_id,
            zone_id=zone.id,
            is_system_default_bucket=False,
            zone_geometry_snapshot=build_route_group_zone_snapshot(
                zone_name=zone.name,
                geometry=zone.geometry,
            ),
            template_snapshot=build_zone_template_snapshot(active_template),
        )
        try:
            with db.session.begin_nested():
                db.session.add(route_group)
                db.session.flush()
        except IntegrityError:
            existing = RouteGroup.query.filter_by(
                route_plan_id=route_plan_id,
                zone_id=zone.id,
                team_id=ctx.team_id,
            ).first()
            if existing is None:
                raise
            created_or_existing.append(existing)
            continue
        created_or_existing.append(route_group)

    recompute_route_group_totals(route_plan)

    db.session.commit()
    return [serialize_route_group(route_group, ctx) for route_group in created_or_existing]
