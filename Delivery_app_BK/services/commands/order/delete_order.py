from __future__ import annotations

from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.exc import NoResultFound

from Delivery_app_BK.errors import NotFound
from Delivery_app_BK.models import Order, RouteGroup, RoutePlan, db
from Delivery_app_BK.services.utils import model_requires_team, require_team_id
from Delivery_app_BK.services.domain.route_operations.plan.recompute_plan_totals import recompute_plan_totals
from Delivery_app_BK.services.domain.state_transitions.order_count_engine import recompute_plan_order_counts
from Delivery_app_BK.services.domain.state_transitions.order_count_engine import (
    recompute_route_group_order_counts,
)
from Delivery_app_BK.services.domain.state_transitions.plan_state_engine import (
    maybe_sync_plan_state_from_groups,
)
from Delivery_app_BK.services.domain.state_transitions.route_group_state_engine import (
    maybe_sync_route_group_state,
)

from ...context import ServiceContext
from ..utils import extract_ids
from .delete_extensions import (
    OrderDeleteDelta,
    apply_order_delete_extensions,
    build_order_delete_extension_context,
)


def delete_order(ctx: ServiceContext):
    target_ids = extract_ids(ctx)
    resolved_orders = _resolve_orders_by_targets(ctx, target_ids)

    ordered_orders: list[Order] = []
    missing_targets: list[int | str] = []
    for target in target_ids:
        order = resolved_orders.get(_target_key(target))
        if not order:
            missing_targets.append(target)
            continue
        ordered_orders.append(order)

    if missing_targets:
        raise NotFound(f"Orders not found: {missing_targets}")

    delete_deltas = [
        OrderDeleteDelta(
            order_id=order.id,
            order_client_id=order.client_id,
                delivery_plan=order.route_plan,
        )
        for order in ordered_orders
    ]

    extension_context = build_order_delete_extension_context(ctx, delete_deltas)
    extension_result = apply_order_delete_extensions(ctx, delete_deltas, extension_context)

    def _apply() -> None:
        # Capture affected plans before deletion so we can recompute totals after flush.
        affected_plans_by_id: dict[int, RoutePlan] = {}
        affected_route_group_ids: set[int] = set()
        for order in ordered_orders:
            plan = getattr(order, "route_plan", None)
            if plan is not None and plan.id is not None:
                affected_plans_by_id[plan.id] = plan
            route_group_id = getattr(order, "route_group_id", None)
            if route_group_id is not None:
                affected_route_group_ids.add(route_group_id)

        for order in ordered_orders:
            db.session.delete(order)
        db.session.flush()

        # After deletion, deleted orders are excluded from SUM — totals now correct.
        for plan in affected_plans_by_id.values():
            recompute_plan_totals(plan)
            recompute_plan_order_counts(plan)

        if affected_route_group_ids:
            route_groups = (
                db.session.query(RouteGroup)
                .filter(RouteGroup.id.in_(affected_route_group_ids))
                .all()
            )
        else:
            route_groups = []

        for route_group in route_groups:
            recompute_route_group_order_counts(route_group)
            maybe_sync_route_group_state(route_group)

        for plan in affected_plans_by_id.values():
            maybe_sync_plan_state_from_groups(plan)

        for action in extension_result.post_flush_actions:
            action()

        if extension_result.instances:
            db.session.add_all(extension_result.instances)

    try:
        with db.session.begin():
            _apply()
    except InvalidRequestError as exc:
        if "already begun" not in str(exc).lower():
            raise
        _apply()
        db.session.commit()

    return {
        "deleted": {
            "order_ids": [order.id for order in ordered_orders],
            "order_client_ids": [order.client_id for order in ordered_orders],
        },
        "updated": extension_result.updated_bundles,
    }


def _resolve_orders_by_targets(
    ctx: ServiceContext,
    target_ids: list[int | str],
) -> dict[tuple[str, str], Order]:
    int_ids = [value for value in target_ids if isinstance(value, int)]
    client_ids = [value for value in target_ids if isinstance(value, str)]

    orders: list[Order] = []
    team_id = None
    if model_requires_team(Order) and ctx.check_team_id:
        team_id = require_team_id(ctx)

    if int_ids:
        query = (
            db.session.query(Order)
            .options(joinedload(Order.route_plan), joinedload(Order.route_group))
            .filter(Order.id.in_(int_ids))
        )
        if team_id is not None:
            query = query.filter(Order.team_id == team_id)
        orders.extend(query.all())

    if client_ids:
        query = (
            db.session.query(Order)
            .options(joinedload(Order.route_plan), joinedload(Order.route_group))
            .filter(Order.client_id.in_(client_ids))
        )
        if team_id is not None:
            query = query.filter(Order.team_id == team_id)
        orders.extend(query.all())

    if not orders:
        raise NoResultFound("No orders found.")

    resolved: dict[tuple[str, str], Order] = {}
    for order in orders:
        if order.id is not None:
            resolved[_target_key(order.id)] = order
        if order.client_id is not None:
            resolved[_target_key(order.client_id)] = order
    return resolved


def _target_key(value: int | str) -> tuple[str, str]:
    if isinstance(value, int):
        return ("id", str(value))
    return ("client_id", str(value))
