from __future__ import annotations

from datetime import datetime
from typing import Any

from Delivery_app_BK.models import Facility, RoutePlan, ZoneTemplate, db
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.route_operations.local_delivery.route_times import (
    ensure_utc_datetime,
    resolve_request_timezone,
)


def build_zone_template_snapshot(template: ZoneTemplate | None) -> dict:
    if template is None:
        return {}

    return {
        "zone_template_id": template.id,
        "name": template.name,
        "version": template.version,
        "default_facility_id": template.default_facility_id,
        "max_orders_per_route": template.max_orders_per_route,
        "max_vehicles": template.max_vehicles,
        "operating_window_start": template.operating_window_start,
        "operating_window_end": template.operating_window_end,
        "eta_tolerance_seconds": template.eta_tolerance_seconds,
        "vehicle_capabilities_required": template.vehicle_capabilities_required,
        "preferred_vehicle_ids": template.preferred_vehicle_ids,
        "default_route_end_strategy": template.default_route_end_strategy,
        "meta": template.meta,
    }


def build_zone_template_route_solution_defaults(
    ctx: ServiceContext,
    plan_instance: RoutePlan,
    template: ZoneTemplate | None,
) -> dict:
    if template is None:
        return {}

    defaults: dict[str, Any] = {}

    if isinstance(template.default_route_end_strategy, str):
        defaults["route_end_strategy"] = template.default_route_end_strategy

    if isinstance(template.eta_tolerance_seconds, int):
        defaults["eta_tolerance_seconds"] = template.eta_tolerance_seconds
        defaults["eta_message_tolerance"] = template.eta_tolerance_seconds

    if isinstance(template.operating_window_start, str):
        defaults["set_start_time"] = template.operating_window_start

    if isinstance(template.operating_window_end, str):
        defaults["set_end_time"] = template.operating_window_end

    facility = None
    if isinstance(template.default_facility_id, int):
        defaults["start_facility_id"] = template.default_facility_id
        facility = db.session.get(Facility, template.default_facility_id)
        if facility is not None and isinstance(facility.property_location, dict):
            defaults["start_location"] = facility.property_location

    if (
        facility is not None
        and ("set_start_time" not in defaults or "set_end_time" not in defaults)
    ):
        facility_open, facility_close = _extract_facility_window_for_plan_day(
            ctx,
            plan_instance,
            facility,
        )
        if "set_start_time" not in defaults and isinstance(facility_open, str):
            defaults["set_start_time"] = facility_open
        if "set_end_time" not in defaults and isinstance(facility_close, str):
            defaults["set_end_time"] = facility_close

    return defaults


def _extract_facility_window_for_plan_day(
    ctx: ServiceContext,
    plan_instance: RoutePlan,
    facility: Facility,
) -> tuple[str | None, str | None]:
    windows = facility.operating_hours
    if not isinstance(windows, list) or not windows:
        return None, None

    weekday = _resolve_plan_weekday(ctx, plan_instance)
    if weekday is None:
        return None, None

    for window in windows:
        if not isinstance(window, dict):
            continue
        day = window.get("day")
        if not isinstance(day, str) or day.strip().lower() != weekday:
            continue

        open_time = window.get("open")
        close_time = window.get("close")
        return (
            open_time if isinstance(open_time, str) else None,
            close_time if isinstance(close_time, str) else None,
        )

    return None, None


def _resolve_plan_weekday(ctx: ServiceContext, plan_instance: RoutePlan) -> str | None:
    start_date = ensure_utc_datetime(getattr(plan_instance, "start_date", None))
    if not isinstance(start_date, datetime):
        return None

    tz = resolve_request_timezone(ctx, plan_instance)
    local_date = start_date.astimezone(tz)
    return local_date.strftime("%a").lower()[:3]
