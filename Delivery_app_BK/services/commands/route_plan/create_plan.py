from datetime import datetime, timezone
from uuid import uuid4

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import (
    db,
    Order,
    RouteGroup,
    RoutePlan,
    RoutePlanState,
    RouteSolution,
    Team,
    User,
    Zone,
    ZoneTemplate,
)
from Delivery_app_BK.route_optimization.constants.is_optimized import (
    IS_OPTIMIZED_NOT_OPTIMIZED,
)
from Delivery_app_BK.services.commands.utils import generate_client_id
from Delivery_app_BK.services.domain.route_operations.local_delivery import (
    normalize_local_delivery_route_solution_defaults,
)
from Delivery_app_BK.services.domain.route_operations.plan.plan_states import PlanStateId
from Delivery_app_BK.services.domain.route_operations.plan.route_group_zone_snapshot import (
    NO_ZONE_SNAPSHOT_NAME,
    build_no_zone_route_group_snapshot,
    build_route_group_zone_snapshot,
)
from Delivery_app_BK.services.domain.order.plan_objective_labels import (
    resolve_route_plan_workflow_type,
)
from Delivery_app_BK.services.domain.route_operations.plan.recompute_route_group_totals import (
    recompute_route_group_totals,
)
from Delivery_app_BK.services.domain.vehicle import select_vehicle_for_route_solution
from Delivery_app_BK.services.infra.events.emiters.order import emit_order_events
from Delivery_app_BK.sockets.emitters.route_solution_events import emit_route_solution_created
from Delivery_app_BK.sockets.notifications import notify_delivery_planning_event
from Delivery_app_BK.services.commands.order.update_order_route_plan import (
    apply_orders_route_plan_change,
)
from Delivery_app_BK.services.requests.route_plan.plan.create_plan import (
    parse_create_plan_request,
)
from Delivery_app_BK.services.commands.route_plan.zone_template_defaults import (
    build_zone_template_route_solution_defaults,
    build_zone_template_snapshot,
)
from ...context import ServiceContext
from ..base.create_instance import create_instance
from ..utils import extract_fields
from .create_serializers import (
    serialize_created_route_plan,
    serialize_created_route_group,
    serialize_created_route_solution,
)


def create_plan(ctx: ServiceContext):
    ctx.set_relationship_map(
        {
            "team_id": Team,
            "state_id": RoutePlanState,
            "orders": Order
        }
    )
    pending_order_events: list[dict] = []
    created_bundles: list[dict] = []
    created_route_solutions: list = []

    create_items = [
        parse_create_plan_request(field_set) for field_set in extract_fields(ctx)
    ]

    def _apply() -> None:
        creation_context: list[dict] = []

        for item in create_items:
            if item.client_id:
                existing_plan = RoutePlan.query.filter_by(
                    team_id=ctx.team_id,
                    client_id=item.client_id,
                ).first()
                if existing_plan is not None:
                    bundle: dict = {"delivery_plan": serialize_created_route_plan(existing_plan)}
                    existing_groups = sorted(
                        list(getattr(existing_plan, "route_groups", None) or []),
                        key=lambda g: g.id,
                    )
                    if existing_groups:
                        bundle["route_groups"] = [
                            serialize_created_route_group(g) for g in existing_groups
                        ]
                        existing_solutions = [
                            s
                            for g in existing_groups
                            for s in (g.route_solutions or [])
                        ]
                        if existing_solutions:
                            bundle["route_solutions"] = [
                                serialize_created_route_solution(s) for s in existing_solutions
                            ]
                    created_bundles.append(bundle)
                    continue

            route_plan_fields = {
                "client_id": item.client_id,
                "label": item.label,
                "date_strategy": item.date_strategy,
                "start_date": item.start_date,
                "end_date": item.end_date,
                "state_id": PlanStateId.OPEN,
            }
            route_plan_instance: RoutePlan = create_instance(
                ctx,
                RoutePlan,
                route_plan_fields,
            )
            creation_context.append(
                {
                    "route_plan": route_plan_instance,
                    "item": item,
                    "route_groups": [],
                    "extra_instances": [],
                    "order_ids": item.order_ids,
                }
            )

        # Flush plans first so their DB-assigned ids are available before
        # route groups are built (route_group.route_plan_id must be non-null).
        db.session.add_all([entry["route_plan"] for entry in creation_context])
        if creation_context:
            db.session.flush()

        # Build route groups now that route_plan_instance.id is populated.
        for entry in creation_context:
            item = entry["item"]
            route_plan_instance = entry["route_plan"]

            no_zone_group, no_zone_solution = _build_no_zone_route_group_instance(
                ctx=ctx,
                route_plan_instance=route_plan_instance,
                route_group_defaults=item.route_group_defaults,
            )
            entry["route_groups"].append(no_zone_group)
            entry["extra_instances"].append(no_zone_solution)

            if item.zone_ids:
                zone_groups, zone_solutions = _build_zone_route_group_instances(
                    ctx=ctx,
                    route_plan_instance=route_plan_instance,
                    zone_ids=item.zone_ids,
                    route_group_defaults=item.route_group_defaults,
                )
                entry["route_groups"].extend(zone_groups)
                entry["extra_instances"].extend(zone_solutions)

        all_route_groups = [
            instance
            for entry in creation_context
            for instance in entry["route_groups"]
        ]
        if all_route_groups:
            db.session.add_all(all_route_groups)
        all_extra_instances = [
            instance
            for entry in creation_context
            for instance in entry["extra_instances"]
        ]
        if all_extra_instances:
            db.session.add_all(all_extra_instances)
        db.session.flush()

        for entry in creation_context:
            linked_order_ids = entry["order_ids"]
            if linked_order_ids:
                outcome = apply_orders_route_plan_change(
                    ctx,
                    linked_order_ids,
                    entry["route_plan"].id,
                )
                pending_order_events.extend(outcome["pending_events"])

        for entry in creation_context:
            if not entry["route_groups"]:
                continue
            recompute_route_group_totals(entry["route_plan"])

        if any(entry["route_groups"] for entry in creation_context):
            db.session.flush()

        for entry in creation_context:
            route_plan_instance: RoutePlan = entry["route_plan"]
            bundle = {
                "delivery_plan": serialize_created_route_plan(route_plan_instance),
            }
            if entry["route_groups"]:
                bundle["route_groups"] = [
                    serialize_created_route_group(route_group_instance)
                    for route_group_instance in entry["route_groups"]
                ]
            local_route_solutions = _find_created_route_solutions(entry["extra_instances"])
            if local_route_solutions:
                bundle["route_solutions"] = [
                    serialize_created_route_solution(route_solution)
                    for route_solution in local_route_solutions
                ]
                created_route_solutions.extend(local_route_solutions)
            created_bundles.append(bundle)

    with db.session.begin():
        _apply()

    if pending_order_events:
        emit_order_events(ctx, pending_order_events)

    actor = db.session.get(User, ctx.user_id) if ctx.user_id else None

    for route_solution in created_route_solutions:
        emit_route_solution_created(route_solution, actor=actor)

    for bundle in created_bundles:
        route_plan_payload = bundle.get("delivery_plan") or {}
        route_plan_id = route_plan_payload.get("id")
        if not isinstance(route_plan_id, int):
            continue
        notify_delivery_planning_event(
            event_id=str(uuid4()),
            event_name="route_plan.created",
            team_id=ctx.team_id,
            entity_type="route_plan",
            entity_id=route_plan_id,
            payload={
                "route_plan_id": route_plan_id,
                "label": route_plan_payload.get("label"),
                "plan_type": resolve_route_plan_workflow_type(),
                "date_strategy": route_plan_payload.get("date_strategy"),
                "route_freshness_updated_at": route_plan_payload.get("updated_at"),
            },
            occurred_at=datetime.now(timezone.utc),
            actor=None,
        )

    return {"created": created_bundles}


def _find_created_route_solutions(extra_instances: list[object]) -> list[RouteSolution]:
    return [
        instance for instance in extra_instances if isinstance(instance, RouteSolution)
    ]


def _build_zone_route_group_instances(
    ctx: ServiceContext,
    route_plan_instance: RoutePlan,
    zone_ids: list[int],
    route_group_defaults: dict,
) -> tuple[list[RouteGroup], list[RouteSolution]]:
    defaults = route_group_defaults if isinstance(route_group_defaults, dict) else {}
    zones = _load_active_zones(ctx, zone_ids)

    route_groups: list[RouteGroup] = []
    route_solutions: list[RouteSolution] = []
    for zone in zones:
        active_template = ZoneTemplate.query.filter_by(
            team_id=ctx.team_id,
            zone_id=zone.id,
            is_active=True,
        ).first()
        template_snapshot = build_zone_template_snapshot(active_template)
        template_route_solution_defaults = build_zone_template_route_solution_defaults(
            ctx,
            route_plan_instance,
            active_template,
        )
        route_group = create_instance(
            ctx,
            RouteGroup,
            {
                "client_id": defaults.get("client_id") or generate_client_id("route_group"),
                "route_plan_id": route_plan_instance.id,
                "state_id": PlanStateId.OPEN,
                "zone_id": zone.id,
                "is_system_default_bucket": False,
                "zone_geometry_snapshot": build_route_group_zone_snapshot(
                    zone_name=zone.name,
                    geometry=zone.geometry,
                ),
                "template_snapshot": template_snapshot,
                "total_orders": 0,
            },
        )
        route_solution = _build_route_solution_instance(
            ctx=ctx,
            route_plan_instance=route_plan_instance,
            route_group=route_group,
            template_route_solution_defaults=template_route_solution_defaults,
            route_group_defaults=defaults,
            zone_template=active_template,
        )
        route_groups.append(route_group)
        route_solutions.append(route_solution)

    return route_groups, route_solutions


def _load_active_zones(ctx: ServiceContext, zone_ids: list[int]) -> list[Zone]:
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
    return [zone_by_id[zone_id] for zone_id in zone_ids]


def _build_route_solution_instance(
    ctx: ServiceContext,
    route_plan_instance: RoutePlan,
    route_group: RouteGroup,
    template_route_solution_defaults: dict,
    route_group_defaults: dict,
    zone_template: ZoneTemplate = None,
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

    # Assign vehicle from zone template preferences if vehicle not explicitly provided
    vehicle_id = normalized_defaults.get("vehicle_id")
    if (
        not vehicle_id
        and zone_template
        and zone_template.preferred_vehicle_ids
    ):
        # Collect vehicle IDs already assigned to other solutions in this route group
        assigned_vehicle_ids = {
            sol.vehicle_id
            for sol in route_group.route_solutions
            if sol.vehicle_id
        }
        
        # Select first available vehicle from preferences or general pool
        vehicle_id = select_vehicle_for_route_solution(
            team_id=ctx.team_id,
            preferred_vehicle_ids=zone_template.preferred_vehicle_ids,
            required_capabilities=zone_template.vehicle_capabilities_required,
            excluded_vehicle_ids=assigned_vehicle_ids,
        )
        if vehicle_id:
            normalized_defaults["vehicle_id"] = vehicle_id

    route_solution = RouteSolution(
        client_id=generate_client_id("route_solution"),
        label="variant 1",
        is_selected=True,
        is_optimized=IS_OPTIMIZED_NOT_OPTIMIZED,
        team_id=ctx.team_id,
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
        vehicle_id=normalized_defaults.get("vehicle_id"),
    )
    route_group.route_solutions.append(route_solution)
    return route_solution


def _extract_route_solution_defaults(route_group_defaults: dict) -> dict:
    route_solution_defaults = route_group_defaults.get("route_solution")
    if not isinstance(route_solution_defaults, dict):
        return {}
    return route_solution_defaults


def _build_no_zone_route_group_instance(
    ctx: ServiceContext,
    route_plan_instance: RoutePlan,
    route_group_defaults: dict,
) -> tuple[RouteGroup, RouteSolution]:
    """Create the default No-Zone RouteGroup and its selected RouteSolution.

    This is called once per new plan.  The idempotency guard in the caller
    (`_apply`) already prevents duplicate plans via client_id, so we do not
    need an extra DB query here.
    """
    route_group = create_instance(
        ctx,
        RouteGroup,
        {
            "client_id": _extract_route_group_client_id(route_group_defaults),
            "route_plan_id": route_plan_instance.id,
            "state_id": PlanStateId.OPEN,
            "zone_id": None,
            "is_system_default_bucket": True,
            "zone_geometry_snapshot": _build_no_zone_snapshot(route_group_defaults),
            "template_snapshot": {},
            "total_orders": 0,
        },
    )
    route_solution = _build_route_solution_instance(
        ctx=ctx,
        route_plan_instance=route_plan_instance,
        route_group=route_group,
        template_route_solution_defaults={},
        route_group_defaults=route_group_defaults if isinstance(route_group_defaults, dict) else {},
    )
    return route_group, route_solution


def _extract_route_group_client_id(route_group_defaults: dict) -> str:
    if not isinstance(route_group_defaults, dict):
        return generate_client_id("route_group")
    candidate = route_group_defaults.get("client_id")
    if isinstance(candidate, str) and candidate.strip():
        return candidate.strip()
    return generate_client_id("route_group")


def _build_no_zone_snapshot(route_group_defaults: dict) -> dict:
    default_snapshot = build_no_zone_route_group_snapshot()
    if not isinstance(route_group_defaults, dict):
        return default_snapshot

    custom_name = route_group_defaults.get("name")
    if isinstance(custom_name, str) and custom_name.strip():
        return {
            "name": custom_name.strip(),
            "geometry": None,
        }
    return {
        "name": NO_ZONE_SNAPSHOT_NAME,
        "geometry": default_snapshot.get("geometry"),
    }
