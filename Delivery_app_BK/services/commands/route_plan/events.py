from typing import Iterable

from Delivery_app_BK.services.infra.events.emiters.route_plan import (
    emit_route_plan_events,
)
from Delivery_app_BK.services.context import ServiceContext


def emit_pending_route_plan_events(
    ctx: ServiceContext,
    pending_events: Iterable[dict],
) -> None:
    events = list(pending_events)
    if not events:
        return
    emit_route_plan_events(ctx, events)


def emit_pending_delivery_plan_events(
    ctx: ServiceContext,
    pending_events: Iterable[dict],
) -> None:
    emit_pending_route_plan_events(ctx, pending_events)
