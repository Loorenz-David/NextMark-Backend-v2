from __future__ import annotations

from sqlalchemy.exc import InvalidRequestError

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.commands.order.update_order_route_plan import (
    update_orders_route_plan,
)
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.order.order_batch_selection import (
    resolve_order_batch_selection,
)
from Delivery_app_BK.services.requests.order.update_orders_route_plan_batch import (
    parse_update_orders_route_plan_batch_payload,
)
from Delivery_app_BK.models import db
from Delivery_app_BK.services.requests.common.types import parse_optional_int


def resolve_orders_selection(ctx: ServiceContext) -> dict:
    selection = parse_update_orders_route_plan_batch_payload(ctx.incoming_data)

    resolved = _run_selection_resolution_transaction(
        lambda: resolve_order_batch_selection(
            ctx=ctx,
            selection=selection,
            endpoint="resolve",
            include_order_ids=False,
        )
    )

    payload = {
        "signature": resolved.signature,
        "resolved_count": resolved.resolved_count,
    }
    if resolved.sample_ids:
        payload["sample_ids"] = resolved.sample_ids
    return payload


def update_orders_route_plan_batch(
    ctx: ServiceContext,
    plan_id: int,
    destination_route_group_id: int | None = None,
) -> dict:
    selection = parse_update_orders_route_plan_batch_payload(ctx.incoming_data)
    resolved = _run_selection_resolution_transaction(
        lambda: resolve_order_batch_selection(
            ctx=ctx,
            selection=selection,
            endpoint="batch_move",
            include_order_ids=True,
        )
    )

    route_group_id = destination_route_group_id
    if route_group_id is None:
        route_group_id = _parse_destination_route_group_id(ctx)

    updated_bundles = []
    if resolved.order_ids:
        updated_payload = update_orders_route_plan(
            ctx,
            resolved.order_ids,
            plan_id,
            destination_route_group_id=route_group_id,
        )
        updated_bundles = updated_payload.get("updated") or []

    return {
        "signature": resolved.signature,
        "resolved_count": resolved.resolved_count,
        "updated_count": len(updated_bundles),
        "updated_bundles": updated_bundles,
    }


def _parse_destination_route_group_id(ctx: ServiceContext) -> int | None:
    incoming = ctx.incoming_data or {}
    if "route_group_id" not in incoming:
        return None
    route_group_id = parse_optional_int(incoming.get("route_group_id"), field="route_group_id")
    if route_group_id is not None and route_group_id <= 0:
        raise ValidationFailed("route_group_id must be greater than 0")
    return route_group_id


def _run_selection_resolution_transaction(resolver):
    try:
        with db.session.begin():
            return resolver()
    except InvalidRequestError as exc:
        if "already begun" not in str(exc).lower():
            raise
        return resolver()
