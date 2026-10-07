from Delivery_app_BK.models import db, Item, Order, RoutePlan
from ....context import ServiceContext
from ...base.delete_instance import delete_instance
from ...utils import extract_ids
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
from Delivery_app_BK.services.infra.audit import record_order_audit_changes_by_order
from Delivery_app_BK.services.domain.order.audit import (
    OrderFieldChange,
    item_deleted_change,
)
from Delivery_app_BK.sockets.emitters.route_plan_events import emit_delivery_plan_totals_updated


def delete_item(ctx: ServiceContext):
    instances = []
    touched_orders: list[Order] = []
    changes_by_order_id: dict[int, list[OrderFieldChange]] = {}
    for target_id in extract_ids(ctx):
        item = get_instance(ctx, Item, target_id)
        if item.order is not None:
            touched_orders.append(item.order)
        if item.order_id is not None:
            changes_by_order_id.setdefault(item.order_id, []).append(
                item_deleted_change(item)
            )
        instances.append(delete_instance(ctx, Item, target_id))
    touch_orders_items_updated_at(touched_orders)
    for order in _unique_orders(touched_orders):
        recompute_order_totals(order)
    for order in _unique_orders(touched_orders):
        recompute_vehicle_warnings_by_order(order)
    for order in _unique_orders(touched_orders):
        touch_route_freshness_by_order(order)
    _recompute_affected_plans(_unique_orders(touched_orders))
    event_id_by_order_id = record_order_audit_changes_by_order(ctx, changes_by_order_id)
    db.session.commit()
    _emit_item_update_events(ctx, touched_orders, event_id_by_order_id)
    _emit_plan_totals_events(_unique_orders(touched_orders))
    return {"_deleted_item_ids": instances, "_affected_orders": _unique_orders(touched_orders)}


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


def _emit_item_update_events(
    ctx: ServiceContext,
    orders: list[Order],
    event_id_by_order_id: dict[int, str],
) -> None:
    unique_orders = _unique_orders(orders)
    if not unique_orders:
        return

    events = []
    for order in unique_orders:
        event = build_order_edited_event(order, changed_sections=["items"])
        if order.id in event_id_by_order_id:
            event["event_id"] = event_id_by_order_id[order.id]
        events.append(event)
    emit_order_events(ctx, events)
