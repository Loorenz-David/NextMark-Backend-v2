from __future__ import annotations

from datetime import datetime, timezone

from Delivery_app_BK.models import OrderEventAction, RoutePlan, Team, db
from Delivery_app_BK.services.commands.integration_logistic.outbound.order import (
    push_order_schedule_update,
)
from Delivery_app_BK.services.domain.order.shopify import is_shopify_order
from Delivery_app_BK.services.infra.events.realtime_refresh import (
    notify_order_event_history_changed,
)


def _truncate_error(error_message: str) -> str:
    if len(error_message) <= 3000:
        return error_message
    return error_message[:3000]


def _mark_action_failed(action: OrderEventAction, error_message: str) -> None:
    action.status = OrderEventAction.STATUS_FAILED
    action.last_error = _truncate_error(error_message)
    db.session.commit()
    notify_order_event_history_changed(action.event_id)


def _mark_action_success(action: OrderEventAction) -> None:
    action.status = OrderEventAction.STATUS_SUCCESS
    action.last_error = None
    action.processed_at = datetime.now(timezone.utc)
    db.session.commit()
    notify_order_event_history_changed(action.event_id)


def _mark_action_skipped(action: OrderEventAction, reason: str) -> None:
    action.status = OrderEventAction.STATUS_SKIPPED
    action.last_error = _truncate_error(reason)
    action.processed_at = datetime.now(timezone.utc)
    db.session.commit()
    notify_order_event_history_changed(action.event_id)


def _resolve_shop_id(order) -> str:
    team = getattr(order, "team", None)
    if team is not None:
        return str(getattr(team, "client_id", "") or "").strip()

    team_id = getattr(order, "team_id", None)
    if team_id is None:
        return ""

    team = db.session.get(Team, team_id)
    return str(getattr(team, "client_id", "") or "").strip()


def _resolve_scheduled_date(order) -> str:
    route_plan = getattr(order, "route_plan", None)
    if route_plan is None and getattr(order, "route_plan_id", None):
        route_plan = db.session.get(RoutePlan, order.route_plan_id)

    if route_plan is None:
        return ""

    start_date = getattr(route_plan, "start_date", None)
    if start_date is None:
        raise ValueError("Order route plan is missing start_date")

    return start_date.date().isoformat()


def push_external_schedule_action(action_id: int) -> None:
    action = db.session.get(OrderEventAction, action_id)
    if action is None:
        return
    if action.status in {OrderEventAction.STATUS_SUCCESS, OrderEventAction.STATUS_SKIPPED}:
        return
    if action.scheduled_for is not None and action.scheduled_for > datetime.now(timezone.utc):
        return

    action.attempts = (action.attempts or 0) + 1
    db.session.commit()

    try:
        if action.event is None or action.event.order is None:
            _mark_action_failed(action, "Order event context is missing")
            return

        order = action.event.order
        if not is_shopify_order(order):
            _mark_action_skipped(action, "Order is not a Shopify external order")
            return

        shop_id = _resolve_shop_id(order)
        if not shop_id:
            _mark_action_skipped(action, "Team shopId is missing")
            return

        order_id = str(getattr(order, "external_order_id", "") or "").strip()
        if not order_id:
            _mark_action_skipped(action, "external_order_id is missing")
            return

        scheduled_date = _resolve_scheduled_date(order)

        result = push_order_schedule_update(
            shop_id=shop_id,
            order_id=order_id,
            scheduled_date=scheduled_date,
        )
        status = (result or {}).get("status")
        reason = (result or {}).get("reason")
        if status == "skipped":
            _mark_action_skipped(action, reason or "External schedule push skipped")
            return

        _mark_action_success(action)
    except Exception as exc:
        _mark_action_failed(action, str(exc))
