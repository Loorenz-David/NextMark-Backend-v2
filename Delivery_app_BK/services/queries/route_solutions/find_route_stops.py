from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Any

from sqlalchemy.orm import Query

from Delivery_app_BK.models import db, RouteSolutionStop
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team
from Delivery_app_BK.services.context import ServiceContext


def find_route_stops(
    params: Dict[str, Any],
    ctx: ServiceContext,
    query: Query | None = None,
) -> Query:
    """
    Build a filtered SQLAlchemy query for RouteSolutionStop records.

    Supported params:
      route_solution_id  — int or list[int]
      order_id           — int or list[int]
      eta_status         — "valid" | "estimated" | "stale"
      in_range           — bool
      has_constraint_violation — bool
      expected_arrival_after  — ISO datetime string
      expected_arrival_before — ISO datetime string
      is_late            — bool (synthetic: actual_arrival_time > expected_arrival_time)
    """
    query = query or db.session.query(RouteSolutionStop)

    if model_requires_team(RouteSolutionStop) and ctx.inject_team_id:
        params = inject_team_id(params, ctx)

    if "team_id" in params:
        query = query.filter(RouteSolutionStop.team_id == params["team_id"])

    if "route_solution_id" in params:
        ids = params["route_solution_id"]
        if not isinstance(ids, (list, tuple)):
            ids = [ids]
        query = query.filter(RouteSolutionStop.route_solution_id.in_(ids))

    if "order_id" in params:
        ids = params["order_id"]
        if not isinstance(ids, (list, tuple)):
            ids = [ids]
        query = query.filter(RouteSolutionStop.order_id.in_(ids))

    if "eta_status" in params:
        query = query.filter(RouteSolutionStop.eta_status == params["eta_status"])

    if "in_range" in params:
        query = query.filter(RouteSolutionStop.in_range.is_(bool(params["in_range"])))

    if "has_constraint_violation" in params:
        query = query.filter(
            RouteSolutionStop.has_constraint_violation.is_(bool(params["has_constraint_violation"]))
        )

    if "expected_arrival_after" in params:
        dt = _parse_dt(params["expected_arrival_after"])
        if dt is not None:
            query = query.filter(RouteSolutionStop.expected_arrival_time >= dt)

    if "expected_arrival_before" in params:
        dt = _parse_dt(params["expected_arrival_before"])
        if dt is not None:
            query = query.filter(RouteSolutionStop.expected_arrival_time <= dt)

    if params.get("is_late") is True or params.get("is_late") == "true":
        # A stop is "late" when it actually arrived after the expected time.
        query = query.filter(
            RouteSolutionStop.actual_arrival_time.isnot(None),
            RouteSolutionStop.actual_arrival_time > RouteSolutionStop.expected_arrival_time,
        )

    # Default ordering: route, then stop sequence
    query = query.order_by(
        RouteSolutionStop.route_solution_id.asc(),
        RouteSolutionStop.stop_order.asc(),
    )

    return query


def _parse_dt(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None
