from __future__ import annotations

from datetime import datetime, time as time_cls, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from Delivery_app_BK.models import Team, db
from Delivery_app_BK.services.context import ServiceContext

DEFAULT_ROUTE_TIME_ZONE = "UTC"


def resolve_request_timezone(
    ctx: ServiceContext | None = None,
    plan_instance: Any | None = None,
    *,
    identity: dict[str, Any] | None = None,
) -> ZoneInfo:
    identity_payload = identity if isinstance(identity, dict) else getattr(ctx, "identity", None) or {}
    identity_tz = _normalize_timezone_name(identity_payload.get("time_zone"))
    if identity_tz:
        return identity_tz

    team_id = _resolve_team_id(ctx, plan_instance)
    if isinstance(team_id, int):
        try:
            team = db.session.get(Team, team_id)
        except RuntimeError:
            team = None
        team_tz = _normalize_timezone_name(getattr(team, "time_zone", None))
        if team_tz:
            return team_tz

    return ZoneInfo(DEFAULT_ROUTE_TIME_ZONE)


def combine_plan_date_and_local_hhmm(
    plan_date: Any,
    hhmm: str | None,
    tz: ZoneInfo,
) -> datetime | None:
    base_date = ensure_utc_datetime(plan_date)
    parsed_time = parse_hhmm(hhmm)
    if base_date is None or parsed_time is None:
        return None

    # Anchor the wall-clock time to the plan's calendar day in the requested
    # local timezone, not the raw UTC calendar date. This preserves the
    # intended local day when a midnight-local plan date is stored as the
    # previous UTC day for positive-offset timezones.
    local_anchor = base_date.astimezone(tz)
    return datetime(
        year=local_anchor.year,
        month=local_anchor.month,
        day=local_anchor.day,
        hour=parsed_time.hour,
        minute=parsed_time.minute,
        second=parsed_time.second,
        tzinfo=tz,
    )


def combine_plan_date_and_local_hhmm_to_utc(
    plan_date: Any,
    hhmm: str | None,
    tz: ZoneInfo,
) -> datetime | None:
    combined = combine_plan_date_and_local_hhmm(plan_date, hhmm, tz)
    if combined is None:
        return None
    return combined.astimezone(timezone.utc)


def ensure_utc_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return None


def parse_hhmm(value: str | None) -> time_cls | None:
    if not isinstance(value, str):
        return None

    parsed = value.strip()
    if not parsed:
        return None

    parts = parsed.split(":")
    if len(parts) not in (2, 3):
        return None

    try:
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) == 3 else 0
        return time_cls(hour=hour, minute=minute, second=second)
    except (TypeError, ValueError):
        return None


def _resolve_team_id(ctx: ServiceContext | None, plan_instance: Any | None) -> int | None:
    plan_team_id = getattr(plan_instance, "team_id", None)
    if isinstance(plan_team_id, int):
        return plan_team_id
    ctx_team_id = getattr(ctx, "team_id", None)
    if isinstance(ctx_team_id, int):
        return ctx_team_id
    return None


def _normalize_timezone_name(value: Any) -> ZoneInfo | None:
    if not isinstance(value, str):
        return None
    name = value.strip()
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return None
