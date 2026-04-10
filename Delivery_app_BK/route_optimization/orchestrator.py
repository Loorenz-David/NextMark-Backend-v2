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
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.outcome import StatusOutcome

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
        request = build_request(context)
        provider = provider or GoogleRouteOptimizationProvider()
     
        result = provider.optimize(request)
       
       
        data = persist_solution(context, request, result, provider.name)
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
