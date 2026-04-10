from typing import List
from datetime import datetime, timezone

from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm.exc import NoResultFound

from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.models import Order, OrderState, RouteGroup, RouteSolution, RouteSolutionStop, db
from Delivery_app_BK.services.domain.state_transitions.order_count_engine import (
    recompute_plan_order_counts,
    recompute_route_group_order_counts,
)
from Delivery_app_BK.services.domain.state_transitions.plan_state_engine import (
    maybe_auto_complete_plan,
    maybe_sync_plan_state_from_groups,
)
from Delivery_app_BK.services.domain.state_transitions.route_group_state_engine import (
    maybe_sync_route_group_state,
)
from Delivery_app_BK.services.infra.events.builders.order import (
    build_order_state_transition_events,
)
from Delivery_app_BK.services.infra.events.emiters.order import emit_order_events
from Delivery_app_BK.services.queries.order.serialize_state_update import (
    build_order_state_update_payload,
)
from Delivery_app_BK.services.utils import (
    ensure_instance_in_team,
    model_requires_team,
    require_team_id,
)

from ....context import ServiceContext
from ....queries.get_instance import get_instance




def update_orders_state(
    ctx: ServiceContext,
    orders: int | List[int] | List[Order],
    state_id: int,
):
    if isinstance(state_id, bool) or not isinstance(state_id, int):
        raise ValidationFailed("state_id must be an integer.")

    changed_orders: list[Order] = []
    pending_events: list[dict] = []

    def _apply() -> list[Order]:
        try:
            state_instance: OrderState = get_instance(ctx, OrderState, state_id)
        except NoResultFound as exc:
            raise NotFound(str(exc)) from exc

        failure_note_payload = _parse_failure_note_payload(
            _extract_incoming_order_note(getattr(ctx, "incoming_data", None))
        )
        is_fail_transition_target = str(getattr(state_instance, "name", "")).strip().casefold() == "fail"

        order_instances: list[Order] = _resolve_orders(ctx, orders)
        if not order_instances:
            return []

        changed_orders.clear()
        pending_events.clear()
        for order_instance in order_instances:
            old_state_id = order_instance.order_state_id
            if old_state_id == state_instance.id:
                continue

            order_instance.order_state_id = state_instance.id
            if is_fail_transition_target and failure_note_payload is not None:
                current_notes = (
                    list(order_instance.order_notes)
                    if isinstance(getattr(order_instance, "order_notes", None), list)
                    else []
                )
                current_notes.append(dict(failure_note_payload))
                order_instance.order_notes = current_notes
            changed_orders.append(order_instance)
            pending_events.extend(
                build_order_state_transition_events(
                    order_instance=order_instance,
                    old_state_id=old_state_id,
                    state_instance=state_instance,
                )
            )

        return changed_orders

    try:
        with db.session.begin():
            changed_orders_result = _apply()
            if changed_orders_result:
                _recompute_and_auto_complete_plans(changed_orders_result)
    except InvalidRequestError as exc:
        if "already begun" not in str(exc).lower():
            raise
        changed_orders_result = _apply()
        if changed_orders_result:
            _recompute_and_auto_complete_plans(changed_orders_result)

    if pending_events:
        emit_order_events(ctx, pending_events)

    return changed_orders_result


def update_orders_state_payload(
    ctx: ServiceContext,
    orders: int | List[int] | List[Order],
    state_id: int,
) -> dict:
    changed_orders = update_orders_state(
        ctx=ctx,
        orders=orders,
        state_id=state_id,
    )
    return build_order_state_update_payload(changed_orders)


def _recompute_and_auto_complete_plans(changed_orders: list[Order]) -> None:
    """
    After order states have been updated, refresh per-state counts on all
    affected delivery plans and auto-complete any that are fully done.
    Runs inside whatever transaction/session is already active.
    """
    affected_plans: dict[int, object] = {}
    affected_route_groups: dict[int, object] = {}
    unresolved_order_ids: list[int] = []
    for order in changed_orders:
        plan = getattr(order, "delivery_plan", None)
        if plan is None:
            plan = getattr(order, "route_plan", None)
        if plan is not None and getattr(plan, "id", None) is not None:
            affected_plans[plan.id] = plan

        route_group = getattr(order, "route_group", None)
        if route_group is None and plan is not None and getattr(order, "route_group_id", None) is not None:
            route_group = next(
                (
                    group
                    for group in (getattr(plan, "route_groups", None) or [])
                    if getattr(group, "id", None) == order.route_group_id
                ),
                None,
            )
        if route_group is not None and getattr(route_group, "id", None) is not None:
            affected_route_groups[route_group.id] = route_group
        else:
            order_id = getattr(order, "id", None)
            if order_id is not None:
                unresolved_order_ids.append(order_id)

    # Fallback path: resolve route groups via route stops for orders that do not
    # have a direct order.route_group relationship set.
    if unresolved_order_ids:
        rows = (
            db.session.query(RouteGroup)
            .join(RouteSolution, RouteSolution.route_group_id == RouteGroup.id)
            .join(RouteSolutionStop, RouteSolutionStop.route_solution_id == RouteSolution.id)
            .filter(RouteSolutionStop.order_id.in_(unresolved_order_ids))
            .all()
        )
        for route_group in rows:
            if route_group is not None and getattr(route_group, "id", None) is not None:
                affected_route_groups[route_group.id] = route_group

    for plan in affected_plans.values():
        recompute_plan_order_counts(plan)
        maybe_auto_complete_plan(plan)

    for route_group in affected_route_groups.values():
        # Recompute order counts for this route group by finding its selected route solution
        route_solutions = getattr(route_group, "route_solutions", None)
        if route_solutions is None:
            route_solutions = (
                db.session.query(RouteSolution)
                .filter(RouteSolution.route_group_id == route_group.id)
                .all()
            )
        selected_solution = next(
            (rs for rs in (route_solutions or []) if getattr(rs, "is_selected", False)),
            None,
        )
        if selected_solution is None and route_solutions:
            selected_solution = route_solutions[0]
        if selected_solution is not None:
            recompute_route_group_order_counts(selected_solution)
        maybe_sync_route_group_state(route_group)

    for plan in affected_plans.values():
        maybe_sync_plan_state_from_groups(plan)



def _resolve_orders(
    ctx: ServiceContext,
    orders: int | List[int] | List[Order],
) -> list[Order]:
    if isinstance(orders, int) and not isinstance(orders, bool):
        try:
            return [get_instance(ctx, Order, orders)]
        except NoResultFound as exc:
            raise NotFound(str(exc)) from exc

    if not isinstance(orders, list):
        raise ValidationFailed("orders must be an integer, a list of integers, or a list of Order instances.")

    if not orders:
        return []

    if all(isinstance(order_id, int) and not isinstance(order_id, bool) for order_id in orders):
        return _resolve_orders_by_ids(ctx, orders)

    if all(isinstance(order, Order) for order in orders):
        return _resolve_order_instances(ctx, orders)

    raise ValidationFailed("orders must contain only integers or only Order instances.")



def _resolve_orders_by_ids(ctx: ServiceContext, order_ids: list[int]) -> list[Order]:
    deduped_ids = list(dict.fromkeys(order_ids))
    query = db.session.query(Order).filter(Order.id.in_(deduped_ids)).with_for_update()
    if model_requires_team(Order) and ctx.check_team_id:
        query = query.filter(Order.team_id == require_team_id(ctx))

    orders = query.all()
    orders_by_id = {order.id: order for order in orders}
    missing_ids = [order_id for order_id in deduped_ids if order_id not in orders_by_id]
    if missing_ids:
        raise NotFound(f"Orders not found: {missing_ids}")

    return [orders_by_id[order_id] for order_id in deduped_ids]


def _resolve_order_instances(ctx: ServiceContext, orders: list[Order]) -> list[Order]:
    deduped_orders: list[Order] = []
    seen_ids: set[int] = set()
    for order in orders:
        if model_requires_team(Order) and ctx.check_team_id:
            ensure_instance_in_team(order, ctx)

        if order.id in seen_ids:
            continue
        seen_ids.add(order.id)
        deduped_orders.append(order)

    return deduped_orders


def _parse_failure_note_payload(raw_note: object) -> dict | None:
    if raw_note is None:
        return None
    if not isinstance(raw_note, dict):
        raise ValidationFailed("order_notes must be a note object with keys: type, content")

    note_type = raw_note.get("type")
    if note_type != "FAILURE":
        raise ValidationFailed("order_notes.type must be 'FAILURE' for state-failure notes")

    content = raw_note.get("content", "")
    if content is None:
        content = ""
    if not isinstance(content, str):
        raise ValidationFailed("order_notes.content must be a string when provided")

    return {
        "type": "FAILURE",
        "content": content,
        "creation_date": datetime.now(timezone.utc).isoformat(),
    }


def _extract_incoming_order_note(incoming_data: object) -> object:
    if not isinstance(incoming_data, dict):
        return None

    direct_note = incoming_data.get("order_notes")
    if direct_note is not None:
        return direct_note

    fields = incoming_data.get("fields")
    if isinstance(fields, dict):
        return fields.get("order_notes")

    return None
