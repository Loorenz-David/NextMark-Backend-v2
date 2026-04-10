from __future__ import annotations

from typing import Dict, Any

from Delivery_app_BK.services.context import ServiceContext
from .find_route_stops import find_route_stops
from .serialize_route_solution_stops import serialize_route_solution_stops


def list_route_stops(params: Dict[str, Any], ctx: ServiceContext) -> dict:
    """
    List RouteSolutionStop records with optional filters and pagination.

    Returns:
      stops        — list of serialized stop dicts
      count        — number of stops in this page
      has_more     — whether additional results exist
    """
    limit = int(params.get("limit", 50))

    query = find_route_stops(params, ctx)
    results = query.limit(limit + 1).all()
    has_more = len(results) > limit
    page = results[:limit]

    serialized = serialize_route_solution_stops(page, ctx)

    return {
        "stops": serialized,
        "count": len(page),
        "has_more": has_more,
    }
