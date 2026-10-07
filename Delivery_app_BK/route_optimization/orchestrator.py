from __future__ import annotations

import logging

from Delivery_app_BK.errors import DomainError
from Delivery_app_BK.route_optimization.providers.base import RouteOptimizationProvider
from Delivery_app_BK.route_optimization.providers.google import (
    GoogleRouteOptimizationProvider,
)
from Delivery_app_BK.route_optimization.services import (
    build_request,
    load_optimization_context,
    persist_solution,
)
from Delivery_app_BK.models import User, db
from Delivery_app_BK.services.commands.route_plan.local_delivery.arrival_tracking import (
    ArrivalSnapshot,
    collect_arrival_changes,
    snapshot_route_arrivals,
)
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.infra.events.emiters.order import emit_order_events
from Delivery_app_BK.services.outcome import StatusOutcome
from Delivery_app_BK.sockets.emitters.route_solution_events import emit_route_solution_updated

logger = logging.getLogger(__name__)


def optimize_route_plan(
    ctx: ServiceContext,
    provider: RouteOptimizationProvider | None = None,
) -> StatusOutcome:
    """
    Root orchestration entrypoint for route plan optimization.
    """
    try:
        context = load_optimization_context(ctx)
        arrival_snapshot = snapshot_route_arrivals(
            context.route_group.team_id, [context.route_group.id]
        )
        request = build_request(context)
        provider = provider or GoogleRouteOptimizationProvider()
     
        result = provider.optimize(request)
       
       
        data = persist_solution(context, request, result, provider.name)
        _announce_optimized_route(ctx, context.route_solution, arrival_snapshot)
        return StatusOutcome(data=data)
    except DomainError as e:
        return StatusOutcome(error=e)
    except Exception as e:
        logger.exception(
            "Unexpected exception in service optimize_route_plan | identity=%s | data=%s",
            ctx.identity,
            ctx.incoming_data,
        )
        return StatusOutcome(error=DomainError("Unexpected internal error"))


def _announce_optimized_route(ctx: ServiceContext, route_solution, arrival_snapshot: ArrivalSnapshot | None) -> None:
    """Refresh other screens, notify once and record the arrivals that moved.
    The optimization is already committed, so a failure here is logged rather
    than turned into a failed request."""
    try:
        arrival_outcome = collect_arrival_changes(arrival_snapshot, cause="route_optimized")
        actor = db.session.get(User, ctx.user_id) if ctx.user_id else None
        emit_route_solution_updated(
            route_solution,
            payload={
                "notification_change_hint": "route_optimized",
                **arrival_outcome.notification_payload,
            },
            actor=actor,
        )
        if arrival_outcome.events:
            emit_order_events(ctx, arrival_outcome.events)
    except Exception:
        logger.exception(
            "Failed to announce optimized route | route_solution_id=%s",
            getattr(route_solution, "id", None),
        )
