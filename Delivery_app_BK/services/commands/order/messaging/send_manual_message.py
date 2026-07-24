from __future__ import annotations

from typing import Any
from uuid import uuid4

from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.models import MessageTemplate, Order, OrderEvent, OrderEventAction, db
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.messaging import (
    MANUAL_ACTION_SCOPE,
    MANUAL_MESSAGE_EVENT_NAME,
    build_manual_action_name,
    validate_manual_channels,
    validate_manual_source_event_id,
    validate_manual_target_orders,
    validate_manual_template_event,
)
from Delivery_app_BK.services.infra.events.action_dispatch import enqueue_order_action
from Delivery_app_BK.services.infra.events.emiters.order import emit_order_events
from Delivery_app_BK.services.infra.events.realtime_refresh import notify_order_action_changed
from Delivery_app_BK.services.infra.messaging.action_scheduling import resolve_enabled_template
from Delivery_app_BK.sockets.emitters.order_message_events import emit_order_message_dispatched


def send_manual_order_message(ctx: ServiceContext) -> dict[str, Any]:
    """
    Sends (or resends) the message template configured for a business event to a
    set of orders, on demand, without the business event having to occur.

    Each target order gets its own manual order event carrying the template
    event in its payload, plus one action per channel that has an enabled
    template. The manual event is written with the event bus disabled, so no
    automatic handler chain runs for it.

    Actions are created for every order first, then announced, then queued, so
    the dispatched frame cannot be overtaken by a worker's status frame.
    """
    payload = ctx.incoming_data or {}

    order_ids = validate_manual_target_orders(payload.get("order_ids"))
    template_event = validate_manual_template_event(payload.get("event"))
    requested_channels = validate_manual_channels(payload.get("channels"))
    source_event_id = validate_manual_source_event_id(payload.get("source_event_id"), order_ids)

    team_id = ctx.team_id
    if team_id is None:
        raise ValidationFailed("Missing team context for a manual message send.")

    templates = _resolve_templates(team_id=team_id, template_event=template_event, channels=requested_channels)
    sendable_channels = [channel for channel in requested_channels if templates[channel] is not None]
    if not sendable_channels:
        raise ValidationFailed(
            f"No enabled message template for event '{template_event}' on channels {requested_channels}."
        )

    orders = _load_orders(order_ids=order_ids, team_id=team_id)
    resolvable_order_ids = [order_id for order_id in order_ids if order_id in orders]

    # Correlates the dispatched frame with every status frame that follows, and
    # gives the client the denominator for a bulk-send progress indicator.
    request_id = uuid4().hex

    source_events = _resolve_source_events(
        order_ids=resolvable_order_ids,
        team_id=team_id,
        template_event=template_event,
        source_event_id=source_event_id,
    )

    manual_events = _emit_manual_events(
        ctx=ctx,
        order_ids=resolvable_order_ids,
        team_id=team_id,
        request_id=request_id,
        template_event=template_event,
        sendable_channels=sendable_channels,
        source_events=source_events,
    )

    results: list[dict[str, Any]] = []
    prepared: list[dict[str, Any]] = []
    for order_id in order_ids:
        if order_id not in orders:
            results.append({"order_id": order_id, "status": "not_found"})
            continue

        prepared_order = _prepare_manual_actions(
            order_id=order_id,
            team_id=team_id,
            request_id=request_id,
            template_event=template_event,
            requested_channels=requested_channels,
            templates=templates,
            manual_event=manual_events[order_id],
            source_event=source_events.get(order_id),
            requested_by=ctx.user_id,
        )
        prepared.append(prepared_order)
        results.append(prepared_order["result"])

    db.session.commit()

    # Published before anything is queued. Emitting after the enqueue loop would
    # let a fast worker's status frame overtake this one on a large batch, since
    # order 1 can be delivered while order 100 is still being queued.
    emit_order_message_dispatched(
        team_id=team_id,
        request_id=request_id,
        template_event=template_event,
        channels=sendable_channels,
        requested_by=ctx.user_id,
        orders=_build_dispatched_frame_orders(results),
        not_found_order_ids=[r["order_id"] for r in results if r["status"] == "not_found"],
    )

    for prepared_order in prepared:
        _enqueue_prepared_actions(prepared_order)

    return {
        "request_id": request_id,
        "event": template_event,
        "channels": sendable_channels,
        "results": results,
    }


def _build_dispatched_frame_orders(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Every action is still PENDING here: the frame is built before anything is
    queued. Skipped channels are omitted because they never produced an action,
    and the request-level `channels` field already tells the client which
    channels the team has configured for this event.
    """
    frame_orders: list[dict[str, Any]] = []

    for result in results:
        if result["status"] != "accepted":
            continue

        actions = [
            {
                "action_id": channel_result["action_id"],
                "channel": channel,
                "status": OrderEventAction.STATUS_PENDING,
            }
            for channel, channel_result in result["channels"].items()
            if "action_id" in channel_result
        ]

        frame_orders.append(
            {
                "order_id": result["order_id"],
                "event_id": result["event_id"],
                "actions": actions,
            }
        )

    return frame_orders


def _resolve_templates(
    *,
    team_id: int,
    template_event: str,
    channels: list[str],
) -> dict[str, MessageTemplate | None]:
    return {
        channel: resolve_enabled_template(team_id=team_id, channel=channel, event_name=template_event)
        for channel in channels
    }


def _load_orders(*, order_ids: list[int], team_id: int) -> dict[int, Order]:
    orders = (
        db.session.query(Order)
        .filter(Order.team_id == team_id, Order.id.in_(order_ids))
        .all()
    )
    return {order.id: order for order in orders}


def _resolve_source_events(
    *,
    order_ids: list[int],
    team_id: int,
    template_event: str,
    source_event_id: int | None,
) -> dict[int, OrderEvent]:
    """
    The source event supplies the payload the message body is rendered from:
    reschedule labels read old/new arrival times straight off the event payload,
    so a resend without it renders a degraded message.
    """
    if not order_ids:
        return {}

    if source_event_id is not None:
        source_event = (
            db.session.query(OrderEvent)
            .filter(
                OrderEvent.id == source_event_id,
                OrderEvent.team_id == team_id,
                OrderEvent.order_id == order_ids[0],
                OrderEvent.event_name == template_event,
            )
            .first()
        )
        if source_event is None:
            raise NotFound(
                f"Order event with id: {source_event_id} does not exist for event "
                f"'{template_event}' on order {order_ids[0]}."
            )
        return {order_ids[0]: source_event}

    candidates = (
        db.session.query(OrderEvent)
        .filter(
            OrderEvent.team_id == team_id,
            OrderEvent.order_id.in_(order_ids),
            OrderEvent.event_name == template_event,
        )
        .order_by(OrderEvent.occurred_at.desc(), OrderEvent.id.desc())
        .all()
    )

    latest_by_order: dict[int, OrderEvent] = {}
    for candidate in candidates:
        latest_by_order.setdefault(candidate.order_id, candidate)
    return latest_by_order


def _build_manual_event_payload(
    *,
    request_id: str,
    template_event: str,
    sendable_channels: list[str],
    requested_by: int | None,
    source_event: OrderEvent | None,
) -> dict[str, Any]:
    source_payload = getattr(source_event, "payload", None)
    payload: dict[str, Any] = dict(source_payload) if isinstance(source_payload, dict) else {}
    payload["manual"] = {
        "request_id": request_id,
        "template_event": template_event,
        "channels": list(sendable_channels),
        "requested_by": requested_by,
        "source_event_id": source_event.id if source_event is not None else None,
    }
    return payload


def _emit_manual_events(
    *,
    ctx: ServiceContext,
    order_ids: list[int],
    team_id: int,
    request_id: str,
    template_event: str,
    sendable_channels: list[str],
    source_events: dict[int, OrderEvent],
) -> dict[int, OrderEvent]:
    if not order_ids:
        return {}

    # prevent_event_bus keeps the manual event out of the dispatcher, so no
    # automatic handler (email, SMS, Shopify fulfillment push) fans out from it.
    emit_ctx = ServiceContext(identity=ctx.identity, prevent_event_bus=True)

    event_rows = emit_order_events(
        emit_ctx,
        [
            {
                "order_id": order_id,
                "event_name": MANUAL_MESSAGE_EVENT_NAME,
                "team_id": team_id,
                "payload": _build_manual_event_payload(
                    request_id=request_id,
                    template_event=template_event,
                    sendable_channels=sendable_channels,
                    requested_by=ctx.user_id,
                    source_event=source_events.get(order_id),
                ),
            }
            for order_id in order_ids
        ],
    )

    return {event_row.order_id: event_row for event_row in event_rows}


def _create_manual_action(
    *,
    manual_event: OrderEvent,
    team_id: int,
    request_id: str,
    template_event: str,
    channel: str,
    requested_by: int | None,
    source_event: OrderEvent | None,
) -> OrderEventAction:
    action = OrderEventAction(
        event_id=manual_event.id,
        action_name=build_manual_action_name(template_event, channel),
        action_scope=MANUAL_ACTION_SCOPE,
        # request_id and channel are carried on the action so the worker can
        # publish a status frame without loading the event row.
        payload={
            "request_id": request_id,
            "template_event": template_event,
            "channel": channel,
            "manual": True,
            "requested_by": requested_by,
            "source_event_id": source_event.id if source_event is not None else None,
        },
        team_id=team_id,
        status=OrderEventAction.STATUS_PENDING,
        attempts=0,
        # A manual send is immediate: no template schedule offset and no future
        # business anchor, so the sender task never defers or re-validates it.
        scheduled_for=None,
        schedule_anchor_type=None,
        schedule_anchor_at=None,
    )
    db.session.add(action)
    db.session.flush()
    return action


def _prepare_manual_actions(
    *,
    order_id: int,
    team_id: int,
    request_id: str,
    template_event: str,
    requested_channels: list[str],
    templates: dict[str, MessageTemplate | None],
    manual_event: OrderEvent,
    source_event: OrderEvent | None,
    requested_by: int | None,
) -> dict[str, Any]:
    """
    Creates the action rows without queueing them, so the caller can publish the
    dispatched frame while every action is still guaranteed to be PENDING.
    """
    channel_results: dict[str, dict[str, Any]] = {}
    created_actions: list[OrderEventAction] = []

    for channel in requested_channels:
        if templates[channel] is None:
            channel_results[channel] = {
                "status": "skipped",
                "detail": f"No enabled {channel} template for event '{template_event}'.",
            }
            continue

        action = _create_manual_action(
            manual_event=manual_event,
            team_id=team_id,
            request_id=request_id,
            template_event=template_event,
            channel=channel,
            requested_by=requested_by,
            source_event=source_event,
        )
        created_actions.append(action)
        channel_results[channel] = {"status": "queued", "action_id": action.id}

    # No relay is enqueued for the manual event: it never reaches the event bus,
    # so the generic order fan-out would produce nothing. The caller publishes a
    # single dispatched frame for the whole request instead.
    return {
        "actions": created_actions,
        "result": {
            "order_id": order_id,
            "status": "accepted",
            "event_id": manual_event.id,
            "source_event_id": source_event.id if source_event is not None else None,
            "channels": channel_results,
        },
    }


def _enqueue_prepared_actions(prepared_order: dict[str, Any]) -> None:
    channel_results = prepared_order["result"]["channels"]

    for action in prepared_order["actions"]:
        channel = action.payload["channel"]
        try:
            enqueue_order_action(action)
        except Exception as exc:
            action.attempts = (action.attempts or 0) + 1
            action.status = OrderEventAction.STATUS_FAILED
            action.last_error = str(exc)
            db.session.commit()
            channel_results[channel] = {
                "status": "failed",
                "action_id": action.id,
                "detail": str(exc),
            }
            # The worker will never run for this action, so nothing else would
            # correct the PENDING state already published in the dispatched frame.
            notify_order_action_changed(action)
