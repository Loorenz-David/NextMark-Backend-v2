from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.commands.route_plan.local_delivery.update_settings import (
    apply_local_delivery_settings_request,
)
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.requests.common.types import parse_optional_time_zone
from Delivery_app_BK.services.requests.route_plan.plan.local_delivery.update_settings import (
    RouteGroupPatchRequest,
    RouteGroupSettingsRequest,
    RoutePlanPatchRequest,
    RouteSolutionPatchRequest,
)

from ._helpers import resolve_driver_route_solution


def adjust_driver_route_dates_to_today(ctx: ServiceContext, route_id: int):
    route_solution = resolve_driver_route_solution(ctx, route_id)
    route_group = getattr(route_solution, "route_group", None)
    route_plan = getattr(route_group, "route_plan", None) if route_group is not None else None

    if route_group is None or route_plan is None:
        raise ValidationFailed("Selected route is missing its route plan context.")

    start_date = _ensure_utc_datetime(getattr(route_plan, "start_date", None))
    end_date = _ensure_utc_datetime(getattr(route_plan, "end_date", None))
    if start_date is None or end_date is None:
        raise ValidationFailed("Route plan has no valid schedule to adjust.")
    if end_date < start_date:
        raise ValidationFailed("Route plan end date cannot be before start date.")

    effective_zone_name = _resolve_time_zone_name(ctx)
    effective_zone = _resolve_time_zone(effective_zone_name)

    if _is_current_local_day_within_range(start_date, end_date, effective_zone):
        return {
            "adjusted": False,
            "route_solution": {
                "id": route_solution.id,
                "client_id": route_solution.client_id,
            },
        }

    duration = end_date - start_date
    new_start = _resolve_today_start_in_utc(effective_zone)
    new_end = new_start + duration

    request = RouteGroupSettingsRequest(
        route_group_id=route_group.id,
        route_plan=RoutePlanPatchRequest(
            start_date=new_start,
            end_date=new_end,
            has_start_date=True,
            has_end_date=True,
        ),
        route_group=RouteGroupPatchRequest(),
        route_solution=RouteSolutionPatchRequest(route_solution_id=route_solution.id),
        create_variant_on_save=False,
        time_zone=effective_zone_name,
    )

    payload = apply_local_delivery_settings_request(
        ctx,
        request,
        reset_route_execution_timing=True,
    )
    payload["adjusted"] = True
    return payload


def _resolve_time_zone_name(ctx: ServiceContext) -> str:
    incoming_data = ctx.incoming_data if isinstance(ctx.incoming_data, dict) else {}
    raw = incoming_data.get("time_zone") if incoming_data else None
    return parse_optional_time_zone(raw, field="time_zone") or ctx.time_zone or "UTC"


def _resolve_time_zone(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _ensure_utc_datetime(value: datetime | None) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _resolve_today_start_in_utc(tz: ZoneInfo) -> datetime:
    now_local = datetime.now(tz)
    start_of_day_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_of_day_local.astimezone(timezone.utc)


def _is_current_local_day_within_range(
    start_date: datetime,
    end_date: datetime,
    tz: ZoneInfo,
) -> bool:
    today_local = datetime.now(tz).date()
    start_local = start_date.astimezone(tz).date()
    end_local = end_date.astimezone(tz).date()
    return start_local <= today_local <= end_local
