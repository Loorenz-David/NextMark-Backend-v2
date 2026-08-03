from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from Delivery_app_BK.models import (
    RouteGroup,
    RoutePlan,
    RouteSolution,
    db,
)

from ....context import ServiceContext
from ...international_shipping_app.apply_order_plan_change import (
    apply_order_plan_change as apply_international_shipping_plan_change,
)
from ...store_pickup_app.apply_order_plan_change import (
    apply_order_plan_change as apply_store_pickup_plan_change,
)
from .route_plan_change import apply_route_plan_change
from .types import PlanChangeApplyContext, PlanChangeResult


PlanChangeHandler = Callable[
    [ServiceContext, object, RoutePlan | None, RoutePlan | None, PlanChangeApplyContext],
    PlanChangeResult,
]


# Which planning domain owns the per-order artifacts on each side of a move.
# International shipping and store pickup are registered as no-ops today; they
# gain real handlers when those domains grow artifacts of their own.
PLAN_CHANGE_HANDLERS: dict[str, PlanChangeHandler] = {
    "local_delivery": apply_route_plan_change,
    "international_shipping": apply_international_shipping_plan_change,
    "store_pickup": apply_store_pickup_plan_change,
}


def apply_order_plan_change(
    ctx: ServiceContext,
    order_instance,
    old_plan: RoutePlan | None,
    new_plan: RoutePlan | None,
    apply_context: PlanChangeApplyContext,
) -> PlanChangeResult:
    if old_plan is None and new_plan is None:
        return PlanChangeResult()

    old_plan_type = _plan_type(old_plan)
    new_plan_type = _plan_type(new_plan)

    # Each domain is handed only the sides that belong to it, so a move within a
    # single domain stays one call. Local delivery depends on that: it merges the
    # stop removal and the stop creation into one incremental route sync, and
    # splitting them would emit two competing resequencing actions.
    results: list[PlanChangeResult] = []
    for plan_type in _ordered_unique(old_plan_type, new_plan_type):
        handler = PLAN_CHANGE_HANDLERS.get(plan_type)
        if handler is None:
            continue

        results.append(
            handler(
                ctx,
                order_instance,
                old_plan if old_plan_type == plan_type else None,
                new_plan if new_plan_type == plan_type else None,
                apply_context,
            )
        )

    return _merge_results(results)


def _plan_type(plan: RoutePlan | None) -> str | None:
    if plan is None:
        return None
    return getattr(plan, "plan_type", None)


def _ordered_unique(*plan_types: str | None) -> list[str]:
    ordered: list[str] = []
    for plan_type in plan_types:
        if plan_type is None or plan_type in ordered:
            continue
        ordered.append(plan_type)
    return ordered


def _merge_results(results: list[PlanChangeResult]) -> PlanChangeResult:
    if not results:
        return PlanChangeResult()
    if len(results) == 1:
        return results[0]

    instances: list[object] = []
    post_flush_actions: list[Callable[[], None]] = []
    for result in results:
        instances.extend(result.instances)
        post_flush_actions.extend(result.post_flush_actions)

    def _serialize_bundle(collected=tuple(results)) -> dict:
        bundle: dict = {}
        for result in collected:
            bundle.update(result.serialize_bundle())
        return bundle

    return PlanChangeResult(
        instances=instances,
        post_flush_actions=post_flush_actions,
        bundle_serializer=_serialize_bundle,
    )


def build_plan_change_apply_context(
    ctx: ServiceContext,
    plan_ids: list[int],
) -> PlanChangeApplyContext:
    deduped_plan_ids = list(dict.fromkeys(plan_ids))
    apply_context = PlanChangeApplyContext()
    if not deduped_plan_ids:
        return apply_context

    _load_local_delivery_context(ctx, deduped_plan_ids, apply_context)

    return apply_context


def _load_local_delivery_context(
    ctx: ServiceContext,
    plan_ids: list[int],
    apply_context: PlanChangeApplyContext,
) -> None:
    route_plan_ids = plan_ids
    route_group_query = db.session.query(RouteGroup).filter(
        RouteGroup.route_plan_id.in_(route_plan_ids)
    )
    if ctx.team_id:
        route_group_query = route_group_query.filter(RouteGroup.team_id == ctx.team_id)

    route_group_instances = route_group_query.all()
    route_groups_by_route_plan_id: defaultdict[int, list[RouteGroup]] = defaultdict(list)
    for route_group in route_group_instances:
        route_groups_by_route_plan_id[route_group.route_plan_id].append(route_group)
    apply_context.route_groups_by_route_plan_id = {
        route_plan_id: sorted(groups, key=lambda group: group.id)
        for route_plan_id, groups in route_groups_by_route_plan_id.items()
    }

    route_group_ids = [instance.id for instance in route_group_instances]
    route_solutions_by_route_group_id: defaultdict[int, list[RouteSolution]] = defaultdict(
        list
    )
    if route_group_ids:
        route_query = db.session.query(RouteSolution).filter(
            RouteSolution.route_group_id.in_(route_group_ids)
        )
        if ctx.team_id:
            route_query = route_query.filter(RouteSolution.team_id == ctx.team_id)

        for route_solution in route_query.all():
            route_solutions_by_route_group_id[
                route_solution.route_group_id
            ].append(route_solution)

    apply_context.route_solutions_by_route_group_id = dict(route_solutions_by_route_group_id)
