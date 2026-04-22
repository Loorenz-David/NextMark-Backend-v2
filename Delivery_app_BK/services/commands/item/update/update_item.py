from Delivery_app_BK.models import db, Item, Order, ItemState, RoutePlan
from ....context import ServiceContext
from ...base.update_instance import update_instance
from ...utils import extract_targets
from ....queries.get_instance import get_instance
from Delivery_app_BK.services.domain.item.order_item_freshness import (
    touch_orders_items_updated_at,
)
from Delivery_app_BK.services.domain.order.recompute_order_totals import recompute_order_totals
from Delivery_app_BK.services.domain.route_operations.plan.recompute_plan_totals import recompute_plan_totals
from Delivery_app_BK.services.domain.vehicle.recompute_vehicle_warnings_by_order import recompute_vehicle_warnings_by_order
from Delivery_app_BK.services.domain.route_operations.plan.route_freshness import touch_route_freshness_by_order
from Delivery_app_BK.services.infra.events.builders.order import build_order_edited_event
from Delivery_app_BK.services.infra.events.emiters.order import emit_order_events
from Delivery_app_BK.sockets.emitters.route_plan_events import emit_delivery_plan_totals_updated


def update_item(ctx: ServiceContext):
    relationship_map = {
        "order_id": Order,
        "item_state_id": ItemState,
    }
    ctx.set_relationship_map(relationship_map)
    instances = []
    touched_orders: list[Order] = []
    for target in extract_targets(ctx):
        existing_item = get_instance(ctx, Item, target["target_id"])
        previous_order = existing_item.order
        instance = update_instance(ctx, Item, target["fields"], target["target_id"])
        instances.append(instance.id)
        if previous_order is not None:
            touched_orders.append(previous_order)
        if instance.order is not None:
            touched_orders.append(instance.order)
    touch_orders_items_updated_at(touched_orders)
    for order in _unique_orders(touched_orders):
        recompute_order_totals(order)
    for order in _unique_orders(touched_orders):
        recompute_vehicle_warnings_by_order(order)
    for order in _unique_orders(touched_orders):
        touch_route_freshness_by_order(order)
    _recompute_affected_plans(_unique_orders(touched_orders))
    db.session.commit()
    _emit_item_update_events(ctx, touched_orders)
    _emit_plan_totals_events(_unique_orders(touched_orders))
    return {"_updated_item_ids": instances, "_affected_orders": _unique_orders(touched_orders)}


def _unique_orders(orders: list[Order]) -> list[Order]:
    unique_by_id: dict[int, Order] = {}
    for order in orders:
        if order is None or getattr(order, "id", None) is None:
            continue
        unique_by_id[order.id] = order
    return list(unique_by_id.values())


def _recompute_affected_plans(orders: list[Order]) -> None:
    seen_plan_ids: set[int] = set()
    for order in orders:
        plan_id = getattr(order, "route_plan_id", None)
        if plan_id is None or plan_id in seen_plan_ids:
            continue
        seen_plan_ids.add(plan_id)
        plan = getattr(order, "route_plan", None) or db.session.get(RoutePlan, plan_id)
        recompute_plan_totals(plan)


def _emit_plan_totals_events(orders: list[Order]) -> None:
    seen_plan_ids: set[int] = set()
    for order in orders:
        plan_id = getattr(order, "route_plan_id", None)
        if plan_id is None or plan_id in seen_plan_ids:
            continue
        seen_plan_ids.add(plan_id)
        plan = getattr(order, "route_plan", None) or db.session.get(RoutePlan, plan_id)
        emit_delivery_plan_totals_updated(plan)


def _emit_item_update_events(ctx: ServiceContext, orders: list[Order]) -> None:
    unique_orders = _unique_orders(orders)
    if not unique_orders:
        return

    emit_order_events(
        ctx,
        [
            build_order_edited_event(order, changed_sections=["items"])
            for order in unique_orders
        ],
    )
