from __future__ import annotations

from collections import defaultdict

from Delivery_app_BK.models import (
    RouteGroup,
    RoutePlan,
    RouteSolution,
    db,
)

from ....context import ServiceContext
from .route_plan_change import apply_route_plan_change
from .types import PlanChangeApplyContext, PlanChangeResult

def apply_order_plan_change(
    ctx: ServiceContext,
    order_instance,
    old_plan: RoutePlan | None,
    new_plan: RoutePlan | None,
    apply_context: PlanChangeApplyContext,
) -> PlanChangeResult:
    if old_plan is None and new_plan is None:
        return PlanChangeResult()

    return apply_route_plan_change(
        ctx=ctx,
        order_instance=order_instance,
        old_plan=old_plan,
        new_plan=new_plan,
        apply_context=apply_context,
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
