from __future__ import annotations

import logging
from datetime import date, timedelta

from Delivery_app_BK.services.analytics.get_breakdowns import get_breakdowns
from Delivery_app_BK.services.analytics.get_metrics import get_metrics
from Delivery_app_BK.services.analytics.get_trends import get_trends
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.analytics.queries.get_daily_metrics import get_daily_metrics
from Delivery_app_BK.analytics.queries.get_route_metrics import get_route_metrics


logger = logging.getLogger(__name__)


def _timeframe_to_days(timeframe: str | None, default_days: int = 7) -> int:
    normalized = (timeframe or "").strip().lower()
    if normalized in {"24h", "1d"}:
        return 1
    if normalized in {"7d", "last_7_days"}:
        return 7
    if normalized in {"30d", "last_30_days"}:
        return 30
    return default_days


def get_analytics_snapshot(ctx: ServiceContext, timeframe: str = "7d") -> dict:
    """Read-only analytics snapshot used by the statistics capability."""
    normalized_timeframe = (timeframe or "7d").strip().lower()
    if normalized_timeframe == "last_7_days":
        normalized_timeframe = "7d"

    metrics = get_metrics(ctx, normalized_timeframe)
    trends_payload = get_trends(ctx, normalized_timeframe)
    breakdowns_payload = get_breakdowns(ctx, normalized_timeframe)

    statuses = [
        metrics.get("data_status") or {},
        trends_payload.get("data_status") or {},
        breakdowns_payload.get("data_status") or {},
    ]
    is_complete = all(status.get("is_complete", True) for status in statuses)
    warnings = [status.get("warning") for status in statuses if status.get("warning")]

    logger.info(
        "Analytics snapshot prepared | timeframe=%s | is_complete=%s | warning_count=%d",
        normalized_timeframe,
        is_complete,
        len(warnings),
    )

    return {
        "metrics": metrics,
        "trends": trends_payload.get("items") or [],
        "breakdowns": breakdowns_payload.get("items") or [],
        "data_status": {
            "is_complete": is_complete,
            "warnings": warnings,
            "components": statuses,
        },
    }


def get_daily_summary(
    ctx: ServiceContext,
    timeframe: str = "7d",
    zone_id: int | None = None,
) -> dict:
    """Return summarized daily analytics facts for the current team."""
    if not ctx.team_id:
        return {"items": [], "summary": {"rows": 0}, "data_status": {"is_complete": False}}

    days_back = _timeframe_to_days(timeframe, default_days=7)
    rows = get_daily_metrics(team_id=ctx.team_id, days_back=days_back, zone_id=zone_id)

    total_created = sum(r.total_orders_created for r in rows)
    total_completed = sum(r.total_orders_completed for r in rows)
    total_failed = sum(r.total_orders_failed for r in rows)

    return {
        "items": [
            {
                "date": r.date.isoformat(),
                "team_id": r.team_id,
                "zone_id": r.zone_id,
                "total_orders_created": r.total_orders_created,
                "total_orders_completed": r.total_orders_completed,
                "total_orders_failed": r.total_orders_failed,
                "completion_rate": r.completion_rate,
                "total_routes": r.total_routes,
                "routes_completed": r.routes_completed,
                "avg_delay_seconds": r.avg_delay_seconds,
            }
            for r in rows
        ],
        "summary": {
            "rows": len(rows),
            "date_from": (date.today() - timedelta(days=days_back)).isoformat(),
            "date_to": date.today().isoformat(),
            "total_orders_created": total_created,
            "total_orders_completed": total_completed,
            "total_orders_failed": total_failed,
            "completion_rate": (total_completed / total_created) if total_created else 0.0,
        },
        "data_status": {"is_complete": True, "warning": None},
    }


def get_route_metrics_tool(
    ctx: ServiceContext,
    days_back: int = 7,
    zone_id: int | None = None,
) -> dict:
    """Return per-route analytics snapshots for the current team."""
    if not ctx.team_id:
        return {"items": [], "summary": {"rows": 0}, "data_status": {"is_complete": False}}

    rows = get_route_metrics(team_id=ctx.team_id, days_back=days_back, zone_id=zone_id)
    return {
        "items": [
            {
                "route_solution_id": r.route_solution_id,
                "team_id": r.team_id,
                "zone_id": r.zone_id,
                "expected_start_time": r.expected_start_time.isoformat() if r.expected_start_time else None,
                "computed_at": r.computed_at.isoformat() if r.computed_at else None,
                "total_stops": r.total_stops,
                "on_time_stops": r.on_time_stops,
                "early_stops": r.early_stops,
                "late_stops": r.late_stops,
                "avg_delay_seconds": r.avg_delay_seconds,
                "max_delay_seconds": r.max_delay_seconds,
                "on_time_rate": r.on_time_rate,
                "delay_rate": r.delay_rate,
                "total_distance_meters": r.total_distance_meters,
                "total_travel_time_seconds": r.total_travel_time_seconds,
                "total_service_time_seconds": r.total_service_time_seconds,
                "total_orders": r.total_orders,
            }
            for r in rows
        ],
        "summary": {
            "rows": len(rows),
            "days_back": days_back,
        },
        "data_status": {"is_complete": True, "warning": None},
    }


def get_zone_metrics(*_args, **_kwargs):
    """Phase 4 placeholder: zone-level metrics endpoint."""
    raise NotImplementedError("Zone metrics will be implemented in Phase 4.")


def get_zone_trends(*_args, **_kwargs):
    """Phase 4 placeholder: zone-level trends endpoint."""
    raise NotImplementedError("Zone trends will be implemented in Phase 4.")
