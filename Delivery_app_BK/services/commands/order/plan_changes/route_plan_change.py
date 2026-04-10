from __future__ import annotations

from collections.abc import Callable

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import RoutePlan, RouteSolution, RouteSolutionStop
from Delivery_app_BK.route_optimization.constants.skip_reasons import (
    ORDER_CHANGE_DELIVERY_PLAN_AFTER_OPTIMIZATION,
)
from Delivery_app_BK.services.commands.order.create_serializers import (
    serialize_created_order_stops,
)
from Delivery_app_BK.services.queries.route_solutions.serialize_route_solutions import (
    serialize_route_solution,
)
from Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.stops import (
    build_route_solution_stops,
    remove_order_stops_for_local_delivery,
)
from Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.plan_sync import (
    build_incremental_route_sync_action,
)

from ....context import ServiceContext
from .types import PlanChangeApplyContext, PlanChangeResult


def apply_route_plan_change(
    ctx: ServiceContext,
    order_instance,
    old_plan: RoutePlan | None,
    new_plan: RoutePlan | None,
    apply_context: PlanChangeApplyContext,
) -> PlanChangeResult:
    instances: list[object] = []
    post_flush_actions: list[Callable[[], None]] = []
    created_stops: list[RouteSolutionStop] = []
    synced_stops: list[RouteSolutionStop] = []
    changed_route_solutions: list[RouteSolution] = []
    starts_by_route_id: dict[int, int] = {}

    if old_plan:
        old_local_delivery = _resolve_route_group_for_plan(
            apply_context=apply_context,
            route_plan_id=old_plan.id,
            selected_route_group_id=apply_context.source_route_group_id_by_order_id.get(
                order_instance.id
            ),
            role="source",
        )

        (
            updated_old_stops,
            updated_old_solutions,
            removed_starts_by_route_id,
        ) = remove_order_stops_for_local_delivery(
            order_instance.id,
            old_local_delivery.id,
        )
        instances.extend(updated_old_stops)
        instances.extend(updated_old_solutions)
        for route_id, start_position in removed_starts_by_route_id.items():
            current = starts_by_route_id.get(route_id)
            starts_by_route_id[route_id] = (
                start_position if current is None else min(current, start_position)
            )

    if new_plan:
        new_local_delivery = _resolve_route_group_for_plan(
            apply_context=apply_context,
            route_plan_id=new_plan.id,
            selected_route_group_id=apply_context.destination_route_group_id_by_order_id.get(
                order_instance.id
            ),
            role="destination",
        )

        route_solutions = list(
            apply_context.route_solutions_by_route_group_id.get(new_local_delivery.id)
            or []
        )
        if not route_solutions:
            raise ValidationFailed("Route solution not found for local delivery plan.")

        stop_instances, stop_links, updated_solutions = build_route_solution_stops(
            ctx,
            order_instance,
            route_solutions,
            skip_reason_for_optimized=ORDER_CHANGE_DELIVERY_PLAN_AFTER_OPTIMIZATION,
        )
        created_stops.extend(stop_instances)
        instances.extend(stop_instances)
        instances.extend(updated_solutions)
        for stop_instance in stop_instances:
            route_id = (
                stop_instance.route_solution_id
                or getattr(getattr(stop_instance, "route_solution", None), "id", None)
            )
            if route_id is None:
                continue
            stop_order = stop_instance.stop_order or 1
            current = starts_by_route_id.get(route_id)
            starts_by_route_id[route_id] = (
                stop_order if current is None else min(current, stop_order)
            )
        post_flush_actions.extend(
            _build_stop_order_link_action(stop_instance, order_instance)
            for stop_instance, order_instance in stop_links
        )

    if starts_by_route_id:
        post_flush_actions.append(
            build_incremental_route_sync_action(
                ctx=ctx,
                starts_by_route_id=starts_by_route_id,
                route_solutions_by_id=_build_route_solutions_by_id(apply_context),
                synced_stops=synced_stops,
                changed_route_solutions=changed_route_solutions,
            )
        )

    return PlanChangeResult(
        instances=instances,
        post_flush_actions=post_flush_actions,
        bundle_serializer=lambda created=created_stops, synced=synced_stops, changed_routes=changed_route_solutions: _serialize_bundle(
            _merge_changed_stops(created, synced),
            _merge_changed_route_solutions(changed_routes),
        ),
    )


def _serialize_bundle(
    stops: list[RouteSolutionStop],
    route_solutions: list[RouteSolution],
) -> dict:
    bundle: dict = {}
    if stops:
        bundle["order_stops"] = serialize_created_order_stops(stops)
    if route_solutions:
        bundle["route_solution"] = [
            serialize_route_solution(route_solution)
            for route_solution in route_solutions
        ]
    return bundle


def _resolve_route_group_for_plan(
    *,
    apply_context: PlanChangeApplyContext,
    route_plan_id: int,
    selected_route_group_id: int | None,
    role: str,
):
    route_groups = apply_context.route_groups_by_route_plan_id.get(route_plan_id) or []
    if not route_groups:
        raise ValidationFailed("Local delivery plan not found for order change.")

    if selected_route_group_id is not None:
        for route_group in route_groups:
            if getattr(route_group, "id", None) == selected_route_group_id:
                return route_group
        raise ValidationFailed(
            f"Selected {role} route_group_id does not belong to the route plan."
        )

    if len(route_groups) == 1:
        return route_groups[0]

    raise ValidationFailed(
        f"Multiple route groups found for route plan; {role} route_group_id is required."
    )


def _build_stop_order_link_action(
    stop_instance: RouteSolutionStop,
    order_instance,
) -> Callable[[], None]:
    def _link() -> None:
        stop_instance.order_id = order_instance.id

    return _link


def _build_route_solutions_by_id(
    apply_context: PlanChangeApplyContext,
) -> dict[int, RouteSolution]:
    route_solutions_by_id: dict[int, object] = {}
    route_solutions_by_group = apply_context.route_solutions_by_route_group_id
    for route_solutions in route_solutions_by_group.values():
        for route_solution in route_solutions:
            if getattr(route_solution, "id", None) is None:
                continue
            route_solutions_by_id[route_solution.id] = route_solution
    return route_solutions_by_id


def _merge_changed_stops(
    created_stops: list[RouteSolutionStop],
    synced_stops: list[RouteSolutionStop],
) -> list[RouteSolutionStop]:
    merged = list(created_stops or []) + list(synced_stops or [])
    deduped: list[RouteSolutionStop] = []
    seen_ids: set[tuple[str, str]] = set()

    for stop in merged:
        stop_id = getattr(stop, "id", None)
        client_id = getattr(stop, "client_id", None)
        key = (
            "id" if stop_id is not None else "client_id",
            str(stop_id if stop_id is not None else client_id),
        )
        if key in seen_ids:
            continue
        seen_ids.add(key)
        deduped.append(stop)

    return sorted(
        deduped,
        key=lambda stop: (
            stop.stop_order if getattr(stop, "stop_order", None) is not None else 10**9,
            getattr(stop, "id", 10**9),
            getattr(stop, "client_id", ""),
        ),
    )


def _merge_changed_route_solutions(
    route_solutions: list[RouteSolution],
) -> list[RouteSolution]:
    deduped: list[RouteSolution] = []
    seen_ids: set[int] = set()
    for route_solution in route_solutions or []:
        route_id = getattr(route_solution, "id", None)
        if route_id is None or route_id in seen_ids:
            continue
        seen_ids.add(route_id)
        deduped.append(route_solution)
    return deduped
