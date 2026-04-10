from __future__ import annotations

from typing import List

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import RouteGroup, Order, RouteSolution, db
from Delivery_app_BK.services.commands.utils import generate_client_id
from Delivery_app_BK.route_optimization.constants.is_optimized import (
    IS_OPTIMIZED_NOT_OPTIMIZED,
)
from Delivery_app_BK.services.domain.route_operations.local_delivery.route_lifecycle import (
    FULL_RECOMPUTE,
    ensure_single_selected_route_solution,
    refresh_local_delivery_route_execution,
)

from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.get_instance import get_instance
from .stops import build_route_solution_stops_for_order_ids
from Delivery_app_BK.services.commands.utils import build_create_result


def create_route_solution(ctx: ServiceContext):
    incoming_data = ctx.incoming_data or {}
    route_group_id = incoming_data.get("route_group_id")
    if not route_group_id:
        raise ValidationFailed("route_group_id is required.")

    allowed_keys = {"route_group_id", "client_id"}
    extra_keys = set(incoming_data.keys()) - allowed_keys
    if extra_keys:
        raise ValidationFailed(f"Unexpected fields: {sorted(extra_keys)}")

    route_group = get_instance(
        ctx=ctx,
        model=RouteGroup,
        value=route_group_id,
    )

    client_id = incoming_data.get("client_id") or generate_client_id('route_solution')

    route_solution = RouteSolution(
        client_id=client_id,
        label="variant 1",
        is_selected=True,
        is_optimized=IS_OPTIMIZED_NOT_OPTIMIZED,
        team_id=ctx.team_id,
        route_group_id=route_group.id,
    )
    route_group.route_solutions.append(route_solution)

    if not route_group.route_plan_id:
        raise ValidationFailed("Route group is missing route_plan_id.")
    order_ids = _get_order_ids(route_group.route_plan_id)
    stop_instances, _updated_solutions = build_route_solution_stops_for_order_ids(
        ctx,
        order_ids,
        [route_solution],
    )

    db.session.add(route_solution)
    if stop_instances:
        db.session.add_all(stop_instances)

    db.session.flush()
    ensure_single_selected_route_solution(
        route_group.id,
        preferred_route_solution_id=route_solution.id,
    )
    if stop_instances:
        route_solution, stop_instances = refresh_local_delivery_route_execution(
            route_solution.id,
            recompute_mode=FULL_RECOMPUTE,
            time_zone=ctx.time_zone,
            warning_sink=ctx,
        )
        db.session.flush()

    route_solution_result = build_create_result(
        ctx,
        [route_solution],
        extract_fields=["id", "label", "is_optimized", "is_selected"],
    )
    route_stop_result = build_create_result(
        ctx,
        stop_instances,
        extract_fields=[
            "id",
            "route_solution_id",
            "order_id",
            "stop_order",
            "in_range",
            "reason_was_skipped",
        ],
    )

    db.session.commit()

    return {
        "route_solution": route_solution_result,
        "route_solution_stop": route_stop_result,
    }


def _get_order_ids(route_plan_id: int) -> List[int]:
    return [
        row[0]
        for row in db.session.query(Order.id)
        .filter(Order.route_plan_id == route_plan_id)
        .all()
    ]
