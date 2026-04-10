from __future__ import annotations
import logging
from datetime import datetime, timezone

from Delivery_app_BK.models import db, RouteSolution
from Delivery_app_BK.models.tables.delivery_plan.delivery_plan import DeliveryPlan
from Delivery_app_BK.errors import NotFound
from Delivery_app_BK.route_optimization.orchestrator import optimize_route_plan as optimize_local_delivery_plan
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.route_plan.get_plan import get_plan as get_plan_service
from Delivery_app_BK.services.queries.route_plan.find_plans import (
    find_plans as list_delivery_plans_service,
)
from Delivery_app_BK.services.commands.route_plan.create_plan import (
    create_plan as create_plan_service,
)
from Delivery_app_BK.services.queries.route_solutions.serialize_route_solutions import (
    serialize_route_solution,
)
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team
from Delivery_app_BK.ai.tools.plan_execution import get_handler

logger = logging.getLogger(__name__)


def optimize_plan_tool(ctx: ServiceContext, local_delivery_plan_id: int) -> dict:
    """Run route optimization for a local delivery plan."""
    ctx.incoming_data["local_delivery_plan_id"] = local_delivery_plan_id
    outcome = optimize_local_delivery_plan(ctx)
    if outcome.error:
        raise outcome.error
    return outcome.data or {"status": "optimized"}


def get_plan_summary_tool(ctx: ServiceContext, plan_id: int) -> dict:
    """Get details of a delivery plan by ID."""
    return get_plan_service(plan_id, ctx)


def list_plans_tool(
    ctx: ServiceContext,
    label: str | None = None,
    plan_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    covers_start: str | None = None,
    covers_end: str | None = None,
    plan_state_id: int | None = None,
    max_orders: int | None = None,
    min_orders: int | None = None,
    limit: int | None = None,
) -> dict:
    """List delivery plans with optional filters."""
    filters = {}
    if label is not None:
        filters["label"] = label
    if plan_type is not None:
        filters["plan_type"] = plan_type
    if start_date is not None:
        filters["start_date"] = start_date
    if end_date is not None:
        filters["end_date"] = end_date
    if covers_start is not None:
        filters["covers_start"] = covers_start
    if covers_end is not None:
        filters["covers_end"] = covers_end
    if plan_state_id is not None:
        filters["plan_state_id"] = plan_state_id
    if max_orders is not None:
        filters["max_orders"] = max_orders
    if min_orders is not None:
        filters["min_orders"] = min_orders
    if limit is not None:
        filters["limit"] = limit
    params = {**ctx.query_params, **filters}
    return list_delivery_plans_service(params, ctx)


def create_plan_tool(
    ctx: ServiceContext,
    label: str,
    start_date: str,
    end_date: str,
    plan_type: str = "local_delivery",
) -> dict:
    """
    Create a new delivery plan.
    Returns the created plan with its ID — use the ID immediately to assign orders.
    """
    ctx.incoming_data = {
        "fields": {
            "label": label,
            "plan_type": plan_type,
            "start_date": start_date,
            "end_date": end_date,
        }
    }
    result = create_plan_service(ctx)
    # result is {"created": [bundles]}; extract the first plan's data
    bundles = result.get("created", []) if isinstance(result, dict) else result
    if isinstance(bundles, list) and bundles:
        bundle = bundles[0]
        plan = bundle.get("delivery_plan") or {}
        return {
            "plan_id": plan.get("id"),
            "label": plan.get("label"),
            "plan_type": plan.get("plan_type"),
            "start_date": plan.get("start_date"),
            "end_date": plan.get("end_date"),
        }
    return {"status": "created", "result": result}


# ---------------------------------------------------------------------------
# Route / driver visibility tools
# ---------------------------------------------------------------------------

def get_plan_execution_status_tool(ctx: ServiceContext, plan_id: int) -> dict:
    """
    Return the execution status for any delivery plan.
    Delegates to a plan-type-specific handler via the strategy registry.
    Adding support for a new plan type = add one handler file + one registry entry.
    """
    plan = db.session.query(DeliveryPlan).filter(DeliveryPlan.id == plan_id).first()
    if not plan:
        raise NotFound(f"Plan {plan_id} not found.")

    handler = get_handler(plan.plan_type)
    if handler is None:
        return {
            "status": "unknown_plan_type",
            "plan_id": plan_id,
            "plan_type": plan.plan_type,
        }

    return handler(ctx, plan)


def list_routes_tool(
    ctx: ServiceContext,
    plan_id: int | None = None,
    date: str | None = None,
    expected_start_after: str | None = None,
    expected_start_before: str | None = None,
    driver_id: int | None = None,
    is_selected: bool = True,
    limit: int = 20,
) -> dict:
    """
    Search RouteSolutions with flexible filters.
    Use this to answer questions like "what route starts at 18:00?" or
    "show me tomorrow's routes".

    Parameters:
      plan_id: filter to a specific plan
      date: ISO date (e.g. "2026-03-20") — returns routes whose expected window covers this date
      expected_start_after: ISO datetime — routes starting at or after this time
      expected_start_before: ISO datetime — routes starting at or before this time
      driver_id: filter by assigned driver
      is_selected: default True — only return the selected/active route per plan
      limit: max results (default 20)

    Tip: to find "routes starting at 18:00 on March 20", combine:
      date="2026-03-20", expected_start_after="2026-03-20T17:55:00",
      expected_start_before="2026-03-20T18:05:00"
    """
    query = db.session.query(RouteSolution).filter(RouteSolution.is_selected.is_(is_selected))

    # Team scope
    if model_requires_team(RouteSolution) and ctx.inject_team_id:
        params: dict = {}
        params = inject_team_id(params, ctx)
        if "team_id" in params:
            query = query.filter(RouteSolution.team_id == params["team_id"])

    if plan_id is not None:
        query = query.filter(RouteSolution.local_delivery_plan_id == plan_id)

    if driver_id is not None:
        query = query.filter(RouteSolution.driver_id == driver_id)

    if date is not None:
        try:
            d = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
            query = query.filter(
                RouteSolution.expected_start_time <= d,
                RouteSolution.expected_end_time >= d,
            )
        except ValueError:
            pass

    if expected_start_after is not None:
        try:
            dt = datetime.fromisoformat(expected_start_after).replace(tzinfo=timezone.utc)
            query = query.filter(RouteSolution.expected_start_time >= dt)
        except ValueError:
            pass

    if expected_start_before is not None:
        try:
            dt = datetime.fromisoformat(expected_start_before).replace(tzinfo=timezone.utc)
            query = query.filter(RouteSolution.expected_start_time <= dt)
        except ValueError:
            pass

    query = query.order_by(RouteSolution.expected_start_time.asc())
    results = query.limit(limit).all()

    return {
        "routes": [serialize_route_solution(r) for r in results],
        "count": len(results),
    }
