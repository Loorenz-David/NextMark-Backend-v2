import logging
from datetime import datetime, timezone
from uuid import uuid4

from Delivery_app_BK.models import Order, User, db
from Delivery_app_BK.sockets.notifications import notify_delivery_planning_event
from Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.update_route_solution_from_plan import (
    update_route_solution_from_plan,
    update_route_solution_from_route_plan,
)
from Delivery_app_BK.services.domain.route_operations.plan.route_freshness import touch_route_freshness
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.order.plan_objective_labels import (
    resolve_route_plan_workflow_type,
)
from Delivery_app_BK.services.requests.route_plan.plan.local_delivery.update_settings import (
    RouteGroupSettingsRequest,
    RouteSolutionPatchRequest,
    parse_update_route_group_settings_request,
    parse_update_local_delivery_settings_request,
)

from ..events import emit_pending_route_plan_events
from .loader import load_route_group_settings_entities
from ..update_plan import apply_route_plan_patch
from .response_builder import build_route_group_settings_response
from .event_helpers import (
    create_route_solution_event,
    create_route_solution_stop_event,
)
from Delivery_app_BK.sockets.contracts.realtime import (
    BUSINESS_EVENT_ROUTE_PLAN_UPDATED,
    BUSINESS_EVENT_ROUTE_SOLUTION_UPDATED,
    BUSINESS_EVENT_ROUTE_SOLUTION_STOP_UPDATED,
)
from Delivery_app_BK.sockets.emitters.route_solution_events import (
    emit_route_solution_updated,
)
from Delivery_app_BK.sockets.emitters.route_solution_stop_events import (
    emit_route_solution_stop_updated,
    notify_route_solution_stops_batch_updated,
)
from Delivery_app_BK.services.domain.vehicle.apply_vehicle_warnings import (
    apply_vehicle_warnings_to_route_solution,
)
from Delivery_app_BK.models.tables.infrastructure.vehicle import Vehicle
from Delivery_app_BK.services.domain.state_transitions.plan_state_engine import (
    apply_plan_state,
    should_reset_plan_to_open,
)
from Delivery_app_BK.services.domain.route_operations.plan.plan_states import PlanStateId
from Delivery_app_BK.services.domain.order.order_states import OrderStateId
from Delivery_app_BK.services.infra.events.builders.order import build_delivery_rescheduled_event
from Delivery_app_BK.services.infra.events.emiters.order import emit_order_events

logger = logging.getLogger(__name__)

def update_local_delivery_settings(ctx: ServiceContext) -> dict:
    incoming_data = ctx.incoming_data or {}
    request: RouteGroupSettingsRequest = parse_update_local_delivery_settings_request(
        incoming_data
    )
    return apply_route_group_settings_request(ctx, request)


def update_route_group_settings(ctx: ServiceContext) -> dict:
    incoming_data = ctx.incoming_data or {}
    request: RouteGroupSettingsRequest = parse_update_route_group_settings_request(
        incoming_data
    )
    return apply_route_group_settings_request(ctx, request)


def apply_route_group_settings_request(
    ctx: ServiceContext,
    request: RouteGroupSettingsRequest,
    *,
    reset_route_execution_timing: bool = False,
) -> dict:
    route_group, route_plan, route_solution = load_route_group_settings_entities(
        ctx=ctx,
        request=request,
    )

    # Capture old driver ID before update
    old_route_solution_driver_id = getattr(route_solution, "driver_id", None)

    previous_start, previous_end, pending_plan_events = apply_route_plan_patch(
        route_plan=route_plan,
        patch=request.route_plan,
    )
    previous_eta_by_order_id = _extract_route_stop_eta_by_order_id(route_solution)

    route_updates = _build_route_solution_updates(request.route_solution)
    effective_time_zone = ctx.time_zone or request.time_zone
    route_solution, stops_changed, original_route_solution = update_route_solution_from_route_plan(
        route_solution=route_solution,
        updates=route_updates,
        plan_start=route_plan.start_date,
        plan_end=route_plan.end_date,
        previous_plan_start=previous_start,
        previous_plan_end=previous_end,
        create_variant_on_save=request.create_variant_on_save,
        time_zone=effective_time_zone,
    )
    if reset_route_execution_timing:
        route_solution.actual_start_time = None
        route_solution.actual_end_time = None
        route_solution.actual_end_time_source = None

    if not hasattr(route_solution, "route_warnings"):
        route_solution.route_warnings = None
    if not hasattr(route_solution, "has_route_warnings"):
        route_solution.has_route_warnings = False

    # Recompute vehicle warnings after all route-solution fields are settled.
    # This runs unconditionally so that a vehicle_id change, a distance refresh,
    # or a vehicle-limit change is always reflected before the commit.
    route_solution_vehicle_id = getattr(route_solution, "vehicle_id", None)
    _vehicle = (
        db.session.get(Vehicle, route_solution_vehicle_id)
        if route_solution_vehicle_id
        else None
    )
    apply_vehicle_warnings_to_route_solution(
        route_solution,
        _vehicle,
        flush=False,
    )

    plan_window_changed = (
        previous_start != route_plan.start_date
        or previous_end != route_plan.end_date
    )
    route_patch_requested = _has_route_solution_patch(request.route_solution)
    route_solution_changed = (
        plan_window_changed
        or route_patch_requested
        or original_route_solution is not None
        or stops_changed
        or reset_route_execution_timing
    )
    route_plan_has_label = getattr(request.route_plan, "has_label", False)
    if plan_window_changed or route_plan_has_label or route_solution_changed:
        touch_route_freshness(route_plan)

    # Reset plan to OPEN when the delivery window or route configuration changes,
    # because any previously computed route may no longer be valid.
    if (plan_window_changed or route_patch_requested) and should_reset_plan_to_open(
        route_plan.state_id
    ):
        apply_plan_state(route_plan, PlanStateId.OPEN)

    db.session.add(route_plan)
    db.session.add(route_group)
    db.session.add(route_solution)
    if original_route_solution is not None:
        db.session.add(original_route_solution)
    if stops_changed:
        db.session.add_all(route_solution.stops or [])
    db.session.commit()

    pending_order_events = _build_order_rescheduled_events_for_route_group_update(
        ctx=ctx,
        route_plan=route_plan,
        previous_plan_start=previous_start,
        previous_plan_end=previous_end,
        previous_eta_by_order_id=previous_eta_by_order_id,
        route_solution=route_solution,
    )
    if pending_order_events:
        emit_order_events(ctx, pending_order_events)

    emit_pending_route_plan_events(ctx, pending_plan_events)

    # Emit real-time events after commit
    team_id = getattr(ctx, "team_id", None)
    actor = db.session.get(User, ctx.user_id) if ctx.user_id else None

    if plan_window_changed or route_plan_has_label:
        notify_delivery_planning_event(
            event_id=str(uuid4()),
            event_name=BUSINESS_EVENT_ROUTE_PLAN_UPDATED,
            team_id=team_id,
            entity_type="route_plan",
            entity_id=route_plan.id,
            payload={
                "route_plan_id": route_plan.id,
                "label": route_plan.label,
                "plan_type": resolve_route_plan_workflow_type(),
                "date_strategy": route_plan.date_strategy,
                "route_freshness_updated_at": route_plan.updated_at.isoformat() if route_plan.updated_at else None,
            },
            occurred_at=route_plan.updated_at or datetime.now(timezone.utc),
            actor=None,
        )
    
    # Emit event if route_solution driver changed (CRITICAL: driver assignment)
    if getattr(route_solution, "driver_id", None) != old_route_solution_driver_id:
        create_route_solution_event(
            ctx=ctx,
            team_id=team_id,
            route_solution_id=route_solution.id,
            event_name=BUSINESS_EVENT_ROUTE_SOLUTION_UPDATED,
            payload={
                "driver_id": getattr(route_solution, "driver_id", None),
                "old_driver_id": old_route_solution_driver_id,
            },
        )
        emit_route_solution_updated(
            route_solution,
            payload={
                "driver_id": getattr(route_solution, "driver_id", None),
                "notification_change_hint": "driver_assigned",
            },
            actor=actor,
        )
    
    # Emit event if route_solution was modified (other than driver assignment)
    if route_solution_changed and getattr(route_solution, "driver_id", None) == old_route_solution_driver_id:
        create_route_solution_event(
            ctx=ctx,
            team_id=team_id,
            route_solution_id=route_solution.id,
            event_name=BUSINESS_EVENT_ROUTE_SOLUTION_UPDATED,
            payload={
                "is_selected": route_solution.is_selected,
                "label": route_solution.label,
            },
        )
        emit_route_solution_updated(
            route_solution,
            payload={"notification_change_hint": "route_optimized"},
            actor=actor,
        )
    
    # Emit socket events for each affected stop (per-stop for precise UI updates).
    # Notifications are suppressed (notify=False); the route-level emit above already
    # notifies when settings changed. If only stops changed (not the route itself),
    # the batch call below fires one notification instead of N.
    if stops_changed and route_solution.stops:
        affected_stops = list(route_solution.stops)
        for stop in affected_stops:
            create_route_solution_stop_event(
                ctx=ctx,
                team_id=team_id,
                route_solution_stop_id=stop.id,
                event_name=BUSINESS_EVENT_ROUTE_SOLUTION_STOP_UPDATED,
                payload={
                    "stop_order": stop.stop_order,
                    "expected_arrival_time": stop.expected_arrival_time.isoformat() if stop.expected_arrival_time else None,
                    "expected_departure_time": stop.expected_departure_time.isoformat() if stop.expected_departure_time else None,
                },
            )
            emit_route_solution_stop_updated(stop, notify=False, actor=actor)

        if not route_solution_changed:
            notify_route_solution_stops_batch_updated(
                route_solution=route_solution,
                affected_stop_count=len(affected_stops),
                change_hint="settings_updated",
                actor=actor,
            )

    return build_route_group_settings_response(
        ctx=ctx,
        route_solution=route_solution,
        stops_changed=stops_changed,
        route_solution_changed=route_solution_changed,
    )


def _extract_route_stop_eta_by_order_id(route_solution) -> dict[int, datetime | None]:
    eta_by_order_id: dict[int, datetime | None] = {}
    for stop in list(getattr(route_solution, "stops", None) or []):
        order_id = getattr(stop, "order_id", None)
        if order_id is None:
            continue
        eta_by_order_id[order_id] = getattr(stop, "expected_arrival_time", None)
    return eta_by_order_id


def _build_order_rescheduled_events_for_route_group_update(
    *,
    ctx: ServiceContext,
    route_plan,
    previous_plan_start: datetime | None,
    previous_plan_end: datetime | None,
    previous_eta_by_order_id: dict[int, datetime | None],
    route_solution,
) -> list[dict]:
    pending_events: list[dict] = []
    emitted_order_ids: set[int] = set()

    if (previous_plan_start, previous_plan_end) != (
        getattr(route_plan, "start_date", None),
        getattr(route_plan, "end_date", None),
    ):
        for order in list(getattr(route_plan, "orders", None) or []):
            if getattr(order, "team_id", None) != ctx.team_id:
                continue
            order_id = getattr(order, "id", None)
            if order_id is None:
                continue
            pending_events.append(
                build_delivery_rescheduled_event(
                    order,
                    old_plan_start=previous_plan_start,
                    old_plan_end=previous_plan_end,
                    new_plan_start=getattr(route_plan, "start_date", None),
                    new_plan_end=getattr(route_plan, "end_date", None),
                    reason="plan_window_changed",
                )
            )
            emitted_order_ids.add(order_id)

    current_eta_by_order_id = _extract_route_stop_eta_by_order_id(route_solution)
    changed_ready_order_ids: list[int] = []
    compared_order_ids = set(previous_eta_by_order_id.keys()) | set(current_eta_by_order_id.keys())
    for order_id in compared_order_ids:
        if order_id in emitted_order_ids:
            continue
        old_eta = previous_eta_by_order_id.get(order_id)
        new_eta = current_eta_by_order_id.get(order_id)
        if old_eta != new_eta:
            changed_ready_order_ids.append(order_id)

    if not changed_ready_order_ids:
        return pending_events

    ready_orders = (
        db.session.query(Order)
        .filter(Order.id.in_(changed_ready_order_ids))
        .filter(Order.team_id == ctx.team_id)
        .filter(Order.order_state_id == OrderStateId.READY)
        .all()
    )
    for order in ready_orders:
        order_id = getattr(order, "id", None)
        if order_id is None:
            continue
        pending_events.append(
            build_delivery_rescheduled_event(
                order,
                old_expected_arrival=previous_eta_by_order_id.get(order_id),
                new_expected_arrival=current_eta_by_order_id.get(order_id),
                reason="eta_changed",
            )
        )

    return pending_events


def apply_local_delivery_settings_request(
    ctx: ServiceContext,
    request: RouteGroupSettingsRequest,
    *,
    reset_route_execution_timing: bool = False,
) -> dict:
    return apply_route_group_settings_request(
        ctx,
        request,
        reset_route_execution_timing=reset_route_execution_timing,
    )


def _build_route_solution_updates(route_patch: RouteSolutionPatchRequest) -> dict:
    updates: dict = {"route_solution_id": route_patch.route_solution_id}

    if getattr(route_patch, "has_start_location", False):
        updates["start_location"] = route_patch.start_location
    if getattr(route_patch, "has_end_location", False):
        updates["end_location"] = route_patch.end_location
    if getattr(route_patch, "has_set_start_time", False):
        updates["set_start_time"] = route_patch.set_start_time
    if getattr(route_patch, "has_set_end_time", False):
        updates["set_end_time"] = route_patch.set_end_time
    if getattr(route_patch, "has_eta_tolerance_seconds", False):
        updates["eta_tolerance_seconds"] = route_patch.eta_tolerance_seconds
    if getattr(route_patch, "has_eta_message_tolerance", False):
        updates["eta_message_tolerance"] = route_patch.eta_message_tolerance
    if getattr(route_patch, "has_route_end_strategy", False):
        updates["route_end_strategy"] = route_patch.route_end_strategy
    if getattr(route_patch, "has_driver_id", False):
        updates["driver_id"] = route_patch.driver_id
    if getattr(route_patch, "has_vehicle_id", False):
        updates["vehicle_id"] = route_patch.vehicle_id
    if getattr(route_patch, "has_stops_service_time", False):
        updates["stops_service_time"] = route_patch.stops_service_time

    return updates


def _has_route_solution_patch(route_patch: RouteSolutionPatchRequest) -> bool:
    return any(
        [
            getattr(route_patch, "has_start_location", False),
            getattr(route_patch, "has_end_location", False),
            getattr(route_patch, "has_set_start_time", False),
            getattr(route_patch, "has_set_end_time", False),
            getattr(route_patch, "has_eta_tolerance_seconds", False),
            getattr(route_patch, "has_eta_message_tolerance", False),
            getattr(route_patch, "has_route_end_strategy", False),
            getattr(route_patch, "has_driver_id", False),
            getattr(route_patch, "has_vehicle_id", False),
            getattr(route_patch, "has_stops_service_time", False),
        ]
    )
