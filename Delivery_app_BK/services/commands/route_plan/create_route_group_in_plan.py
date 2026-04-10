from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.models import RouteGroup, RoutePlan, RouteSolution, Zone, ZoneTemplate, db
from Delivery_app_BK.route_optimization.constants.is_optimized import IS_OPTIMIZED_NOT_OPTIMIZED
from Delivery_app_BK.services.commands.utils import generate_client_id
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.route_operations.local_delivery import (
    normalize_local_delivery_route_solution_defaults,
)
from Delivery_app_BK.services.domain.route_operations.plan.plan_states import PlanStateId
from Delivery_app_BK.services.domain.route_operations.plan.recompute_route_group_totals import (
    recompute_route_group_totals,
)
from Delivery_app_BK.services.domain.route_operations.plan.route_group_zone_snapshot import (
    NO_ZONE_SNAPSHOT_NAME,
    build_route_group_zone_snapshot,
)
from Delivery_app_BK.services.queries.route_plan.plan_types.serialize_route_group import (
    serialize_route_group,
)
from Delivery_app_BK.services.requests.route_plan.plan.create_route_group import (
    parse_create_route_group_request,
)
from Delivery_app_BK.services.commands.route_plan.zone_template_defaults import (
    build_zone_template_route_solution_defaults,
    build_zone_template_snapshot,
)


def create_route_group_in_plan(ctx: ServiceContext) -> dict:
    raw_payload = ctx.incoming_data or {}
    payload_for_validation = {
        key: value for key, value in raw_payload.items() if key != "route_plan_id"
    }
    request = parse_create_route_group_request(
        payload_for_validation,
        route_plan_id=raw_payload.get("route_plan_id"),
    )

    route_plan = db.session.get(RoutePlan, request.route_plan_id)
    if route_plan is None or route_plan.team_id != ctx.team_id:
        raise NotFound(f"Route plan {request.route_plan_id} not found")

    defaults = request.route_group_defaults if isinstance(request.route_group_defaults, dict) else {}

    if request.zone_id is not None:
        return _create_or_get_zone_route_group(ctx, route_plan, request.zone_id, defaults)
    return _create_manual_no_zone_route_group(ctx, route_plan, defaults)


def _create_or_get_zone_route_group(
    ctx: ServiceContext,
    route_plan: RoutePlan,
    zone_id: int,
    route_group_defaults: dict,
) -> dict:
    zone = db.session.get(Zone, zone_id)
    if zone is None or zone.team_id != ctx.team_id or not zone.is_active:
        raise ValidationFailed(f"Invalid zone_id for this team: {zone_id}")

    existing = RouteGroup.query.filter_by(
        team_id=ctx.team_id,
        route_plan_id=route_plan.id,
        zone_id=zone_id,
    ).first()
    if existing is not None:
        selected_solution = _resolve_selected_solution(existing)
        return {
            "created": False,
            "route_group": serialize_route_group(existing, ctx),
            "route_solution": _serialize_route_solution_light(selected_solution),
        }

    active_template = ZoneTemplate.query.filter_by(
        team_id=ctx.team_id,
        zone_id=zone.id,
        is_active=True,
    ).first()
    template_snapshot = build_zone_template_snapshot(active_template)
    template_route_solution_defaults = build_zone_template_route_solution_defaults(
        ctx,
        route_plan,
        active_template,
    )

    route_group = RouteGroup(
        team_id=ctx.team_id,
        client_id=_extract_route_group_client_id(route_group_defaults),
        route_plan_id=route_plan.id,
        state_id=PlanStateId.OPEN,
        zone_id=zone.id,
        is_system_default_bucket=False,
        zone_geometry_snapshot=build_route_group_zone_snapshot(
            zone_name=zone.name,
            geometry=zone.geometry,
        ),
        template_snapshot=template_snapshot,
        total_orders=0,
    )
    route_solution = _build_route_solution_instance(
        ctx=ctx,
        route_plan_instance=route_plan,
        route_group=route_group,
        template_route_solution_defaults=template_route_solution_defaults,
        route_group_defaults=route_group_defaults,
    )

    try:
        with db.session.begin_nested():
            db.session.add(route_group)
            db.session.add(route_solution)
            db.session.flush()
    except IntegrityError:
        existing = RouteGroup.query.filter_by(
            team_id=ctx.team_id,
            route_plan_id=route_plan.id,
            zone_id=zone.id,
        ).first()
        if existing is None:
            raise
        selected_solution = _resolve_selected_solution(existing)
        return {
            "created": False,
            "route_group": serialize_route_group(existing, ctx),
            "route_solution": _serialize_route_solution_light(selected_solution),
        }

    recompute_route_group_totals(route_plan)
    db.session.commit()

    return {
        "created": True,
        "route_group": serialize_route_group(route_group, ctx),
        "route_solution": _serialize_route_solution_light(route_solution),
    }


def _create_manual_no_zone_route_group(
    ctx: ServiceContext,
    route_plan: RoutePlan,
    route_group_defaults: dict,
) -> dict:
    route_group = RouteGroup(
        team_id=ctx.team_id,
        client_id=_extract_route_group_client_id(route_group_defaults),
        route_plan_id=route_plan.id,
        state_id=PlanStateId.OPEN,
        zone_id=None,
        is_system_default_bucket=False,
        zone_geometry_snapshot={
            "name": _extract_no_zone_name(route_group_defaults),
            "geometry": None,
        },
        template_snapshot={},
        total_orders=0,
    )
    route_solution = _build_route_solution_instance(
        ctx=ctx,
        route_plan_instance=route_plan,
        route_group=route_group,
        template_route_solution_defaults={},
        route_group_defaults=route_group_defaults,
    )

    db.session.add(route_group)
    db.session.add(route_solution)
    db.session.flush()
    recompute_route_group_totals(route_plan)
    db.session.commit()

    return {
        "created": True,
        "route_group": serialize_route_group(route_group, ctx),
        "route_solution": _serialize_route_solution_light(route_solution),
    }


def _build_route_solution_instance(
    ctx: ServiceContext,
    route_plan_instance: RoutePlan,
    route_group: RouteGroup,
    template_route_solution_defaults: dict,
    route_group_defaults: dict,
) -> RouteSolution:
    normalized_defaults = normalize_local_delivery_route_solution_defaults(
        ctx,
        route_plan_instance,
        {
            "route_solution": {
                **template_route_solution_defaults,
                **_extract_route_solution_defaults(route_group_defaults),
            }
        },
    )

    return RouteSolution(
        client_id=generate_client_id("route_solution"),
        label="variant 1",
        is_selected=True,
        is_optimized=IS_OPTIMIZED_NOT_OPTIMIZED,
        team_id=ctx.team_id,
        route_group=route_group,
        start_location=normalized_defaults["start_location"],
        end_location=normalized_defaults["end_location"],
        set_start_time=normalized_defaults["set_start_time"],
        expected_start_time=normalized_defaults["expected_start_time"],
        set_end_time=normalized_defaults["set_end_time"],
        eta_tolerance_seconds=normalized_defaults["eta_tolerance_seconds"],
        eta_message_tolerance=normalized_defaults["eta_message_tolerance"],
        stops_service_time=normalized_defaults["stops_service_time"],
        route_end_strategy=normalized_defaults["route_end_strategy"],
        driver_id=normalized_defaults["driver_id"],
        start_facility_id=normalized_defaults["start_facility_id"],
    )


def _extract_route_solution_defaults(route_group_defaults: dict) -> dict:
    route_solution_defaults = route_group_defaults.get("route_solution")
    if not isinstance(route_solution_defaults, dict):
        return {}
    return route_solution_defaults


def _extract_route_group_client_id(route_group_defaults: dict) -> str:
    candidate = route_group_defaults.get("client_id")
    if isinstance(candidate, str) and candidate.strip():
        return candidate.strip()
    return generate_client_id("route_group")


def _extract_no_zone_name(route_group_defaults: dict) -> str:
    name = route_group_defaults.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return NO_ZONE_SNAPSHOT_NAME


def _resolve_selected_solution(route_group: RouteGroup) -> RouteSolution | None:
    route_solutions = list(getattr(route_group, "route_solutions", None) or [])
    if not route_solutions:
        return None
    selected = next(
        (solution for solution in route_solutions if getattr(solution, "is_selected", False)),
        route_solutions[0],
    )
    return selected


def _serialize_route_solution_light(route_solution: RouteSolution | None) -> dict | None:
    if route_solution is None:
        return None
    return {
        "id": route_solution.id,
        "client_id": route_solution.client_id,
        "is_selected": route_solution.is_selected,
        "is_optimized": route_solution.is_optimized,
        "route_group_id": route_solution.route_group_id,
        "start_location": route_solution.start_location,
        "end_location": route_solution.end_location,
        "set_start_time": route_solution.set_start_time,
        "set_end_time": route_solution.set_end_time,
        "eta_tolerance_seconds": route_solution.eta_tolerance_seconds,
        "eta_message_tolerance": route_solution.eta_message_tolerance if route_solution.eta_message_tolerance is not None else 1800,
        "stops_service_time": route_solution.stops_service_time,
    }
