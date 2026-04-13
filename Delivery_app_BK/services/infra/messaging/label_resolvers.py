from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import TYPE_CHECKING, Callable

from Delivery_app_BK.models import RouteSolution, RouteSolutionStop, Team, db

if TYPE_CHECKING:
    from Delivery_app_BK.models import RoutePlanEvent, Order, OrderEvent


class MessageRenderContext:
    def __init__(
        self,
        order: "Order",
        order_event: "OrderEvent | None" = None,
        team_id: int | None = None,
        team_time_zone: str | None = None,
        route_plan_event: "RoutePlanEvent | None" = None,
        extra_context: dict[str, object] | None = None,
    ) -> None:
        self.order = order
        self.order_event = order_event
        self.route_plan_event = route_plan_event
        self.team_id = team_id
        self.team_time_zone = team_time_zone
        self.extra_context = extra_context or {}
        self._selected_route_stop_loaded = False
        self._selected_route_stop: RouteSolutionStop | None = None
        self._selected_route_solution_loaded = False
        self._selected_route_solution: RouteSolution | None = None
        self._resolved_team_time_zone_loaded = False
        self._resolved_team_time_zone: str | None = None

    def get_selected_route_stop(self) -> RouteSolutionStop | None:
        if self._selected_route_stop_loaded:
            return self._selected_route_stop

        query = (
            db.session.query(RouteSolutionStop)
            .join(RouteSolution, RouteSolutionStop.route_solution_id == RouteSolution.id)
            .filter(
                RouteSolutionStop.order_id == self.order.id,
                RouteSolution.is_selected.is_(True),
            )
            .order_by(RouteSolutionStop.stop_order.asc(), RouteSolutionStop.id.asc())
        )

        if self.team_id is not None:
            query = query.filter(
                RouteSolutionStop.team_id == self.team_id,
                RouteSolution.team_id == self.team_id,
            )

        self._selected_route_stop = query.first()
        self._selected_route_stop_loaded = True
        return self._selected_route_stop

    def get_selected_route_solution(self) -> RouteSolution | None:
        if self._selected_route_solution_loaded:
            return self._selected_route_solution

        stop = self.get_selected_route_stop()
        if stop is None:
            self._selected_route_solution_loaded = True
            return None

        route_solution_id = getattr(stop, "route_solution_id", None)
        if route_solution_id is None:
            self._selected_route_solution_loaded = True
            return None

        query = db.session.query(RouteSolution).filter(RouteSolution.id == route_solution_id)
        if self.team_id is not None:
            query = query.filter(RouteSolution.team_id == self.team_id)

        self._selected_route_solution = query.first()
        self._selected_route_solution_loaded = True
        return self._selected_route_solution

    def get_team_time_zone(self) -> str:
        if self._resolved_team_time_zone_loaded:
            return self._resolved_team_time_zone or "UTC"

        candidate = self.team_time_zone
        if not isinstance(candidate, str) or not candidate.strip():
            candidate = None

        if candidate is None and self.team_id is not None:
            team = db.session.get(Team, self.team_id)
            candidate = getattr(team, "time_zone", None) if team is not None else None

        if not isinstance(candidate, str) or not candidate.strip():
            candidate = "UTC"

        self._resolved_team_time_zone = candidate
        self._resolved_team_time_zone_loaded = True
        return candidate


LabelResolver = Callable[[MessageRenderContext, str], str]


def _to_string(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _format_short_date(value: datetime) -> str:
    return f"{value.strftime('%b')} {value.day}"


def _format_customer_eta_window(
    *,
    start_time: datetime,
    end_time: datetime,
    reference_time: datetime,
) -> str:
    start_label = start_time.strftime("%H:%M")
    end_label = end_time.strftime("%H:%M")

    if start_time.date() == reference_time.date():
        if end_time.date() == start_time.date():
            return f"today {start_label} to {end_label}"
        return f"today {start_label} to {_format_short_date(end_time)} {end_label}"

    if start_time.date() == end_time.date():
        return f"{_format_short_date(start_time)} {start_label} to {end_label}"

    return (
        f"{_format_short_date(start_time)} {start_label} "
        f"to {_format_short_date(end_time)} {end_label}"
    )


def _resolve_client_first_name(context: MessageRenderContext, channel: str) -> str:
    return _to_string(getattr(context.order, "client_first_name", None))


def _resolve_client_last_name(context: MessageRenderContext, channel: str) -> str:
    return _to_string(getattr(context.order, "client_last_name", None))


def _resolve_tracking_number(context: MessageRenderContext, channel: str) -> str:
    return _to_string(getattr(context.order, "tracking_number", None))


def _resolve_plan_delivery_date_display(context: MessageRenderContext, channel: str) -> str:
    route_plan_event = context.route_plan_event
    if route_plan_event is None:
        return ""
    route_plan = route_plan_event.route_plan
    if route_plan is None:
        return ""

    start_date = getattr(route_plan, "start_date", None)
    end_date = getattr(route_plan, "end_date", None)
    if not isinstance(start_date, datetime) or not isinstance(end_date, datetime):
        return ""
    
    if start_date.date() == end_date.date():
        return start_date.strftime("%Y-%m-%d")
    else:
        return f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"  






def _round_to_nearest_30(dt: datetime) -> datetime:
    from datetime import timedelta
    minute = dt.minute
    if minute < 15:
        rounded_minute = 0
    elif minute < 45:
        rounded_minute = 30
    else:
        dt = dt + timedelta(hours=1)
        rounded_minute = 0
    return dt.replace(minute=rounded_minute, second=0, microsecond=0)


def _get_eta_tolerance_minutes(context: MessageRenderContext) -> int:
    route_solution = context.get_selected_route_solution()
    tolerance_seconds = getattr(route_solution, "eta_message_tolerance", None)
    if not isinstance(tolerance_seconds, int) or isinstance(tolerance_seconds, bool):
        tolerance_seconds = 1800
    return max(0, tolerance_seconds // 60)


def _resolve_expected_arrival_time(context: MessageRenderContext, channel: str, range_minutes: int = 0) -> str:
    from datetime import timedelta
    stop = context.get_selected_route_stop()
    if stop is None:
        return ""

    arrival_time = getattr(stop, "expected_arrival_time", None)
    if not isinstance(arrival_time, datetime):
        return ""

    try:
        arrival_time = arrival_time.astimezone(ZoneInfo(context.get_team_time_zone()))
    except Exception:
        arrival_time = arrival_time.astimezone(ZoneInfo("UTC"))

    reference_time = datetime.now(arrival_time.tzinfo)
    arrival_time = _round_to_nearest_30(arrival_time)

    if range_minutes > 0:
        start_time = arrival_time - timedelta(minutes=range_minutes)
        end_time = arrival_time + timedelta(minutes=range_minutes)
        return _format_customer_eta_window(
            start_time=start_time,
            end_time=end_time,
            reference_time=reference_time,
        )
    if arrival_time.date() == reference_time.date():
        return f"today {arrival_time.strftime('%H:%M')}"
    return f"{_format_short_date(arrival_time)} {arrival_time.strftime('%H:%M')}"


def _resolve_expected_arrival_time_costumer(context: MessageRenderContext, channel: str) -> str:
    return _resolve_expected_arrival_time(
        context,
        channel,
        range_minutes=_get_eta_tolerance_minutes(context),
    )

def _resolve_tracking_link(context: MessageRenderContext, channel: str) -> str:
    return _to_string(getattr(context.order, "tracking_link", None))


def _resolve_client_form_link(context: MessageRenderContext, channel: str) -> str:
    return _to_string(context.extra_context.get("client_form_link"))


def _parse_reschedule_window(
    context: MessageRenderContext,
) -> tuple[datetime | None, datetime | None, datetime | None, datetime | None]:
    """
    Returns (old_start, old_end, new_start, new_end) from a DELIVERY_RESCHEDULED
    event payload, converted to the team's timezone.

    For every reason, expected_arrival values take priority over plan window dates
    because they are per-order (computed by route optimisation) and more precise.
    Plan window dates are used as fallback when arrivals are absent.

    - eta_changed             → arrivals only, no window end
    - plan_window_changed     → arrivals if present, otherwise plan window
    - plan_move_date_changed  → arrivals if present, otherwise plan window
    """
    order_event = context.order_event
    if order_event is None:
        return None, None, None, None

    payload = getattr(order_event, "payload", None) or {}
    reason = payload.get("reason")
    tz_str = context.get_team_time_zone()

    def _parse(raw: object) -> datetime | None:
        if not isinstance(raw, str):
            return None
        try:
            return datetime.fromisoformat(raw).astimezone(ZoneInfo(tz_str))
        except Exception:
            return None

    old_arrival = _parse(payload.get("old_expected_arrival"))
    new_arrival = _parse(payload.get("new_expected_arrival"))

    if reason == "eta_changed":
        return old_arrival, None, new_arrival, None

    old_plan_start = _parse(payload.get("old_plan_start"))
    old_plan_end = _parse(payload.get("old_plan_end"))
    new_plan_start = _parse(payload.get("new_plan_start"))
    new_plan_end = _parse(payload.get("new_plan_end"))

    # Prefer per-order arrival times; fall back to plan window bounds.
    old_start = old_arrival if old_arrival is not None else old_plan_start
    old_end = None if old_arrival is not None else old_plan_end
    new_start = new_arrival if new_arrival is not None else new_plan_start
    new_end = None if new_arrival is not None else new_plan_end

    return old_start, old_end, new_start, new_end


def _resolve_reschedule_time(context: MessageRenderContext, channel: str) -> str:
    from datetime import timedelta

    # New side: resolved from the route stop via context — the same mechanism
    # used by expected_arrival_time_costumer. Team timezone and tolerance are
    # already handled there, so no conversion is needed here.
    range_minutes = _get_eta_tolerance_minutes(context)
    new_time_str = _resolve_expected_arrival_time(context, channel, range_minutes=range_minutes)
    if not new_time_str:
        return ""

    stop = context.get_selected_route_stop()
    raw_new_eta = getattr(stop, "expected_arrival_time", None) if stop else None
    if raw_new_eta is None:
        return new_time_str

    try:
        new_date = raw_new_eta.astimezone(ZoneInfo(context.get_team_time_zone())).date()
    except Exception:
        new_date = raw_new_eta.astimezone(ZoneInfo("UTC")).date()

    # Old side: from payload, converted to team timezone.
    old_start, old_end, _, _ = _parse_reschedule_window(context)

    if old_start is not None and old_end is None:
        old_start = _round_to_nearest_30(old_start)
        if range_minutes > 0:
            old_end = old_start + timedelta(minutes=range_minutes)
            old_start = old_start - timedelta(minutes=range_minutes)

    def _fmt_time(start: datetime, end: datetime | None) -> str:
        if end is not None:
            return f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')}"
        return start.strftime("%H:%M")

    if old_start is None:
        return new_time_str

    date_changed = old_start.date() != new_date
    old_time_str = _fmt_time(old_start, old_end)
    time_changed = old_time_str != new_time_str

    if date_changed and time_changed:
        return f"{_format_short_date(old_start)}, {old_time_str} → {new_time_str}"

    if date_changed:
        return f"{_format_short_date(old_start)} → {_format_short_date(new_date)}"

    if time_changed:
        return f"{old_time_str} → {new_time_str}"

    return new_time_str


def phone_to_string(phone_data: object) -> str:
    if isinstance(phone_data, str):
        return phone_data
    
    if isinstance(phone_data, dict):
        prefix = phone_data.get("prefix")
        if isinstance(prefix, str):
            number = phone_data.get("number")
            if isinstance(number, str):
                return f"{prefix}{number}"
        number = phone_data.get("number")
        if isinstance(number, str):
            return number
    return ""

def _resolve_client_phone_number(context: MessageRenderContext, channel: str, is_secondary: bool = False) -> str:
    primary_phone_data = getattr(context.order, "client_primary_phone", None)
    secondary_phone_data = getattr(context.order, "client_secondary_phone", None)
    if primary_phone_data is None and secondary_phone_data is None:
        return ""
    if is_secondary:
        return phone_to_string(secondary_phone_data)
    return phone_to_string(primary_phone_data)
   
    return ""

def _resolve_client_address(context: MessageRenderContext, channel: str) -> str:
    address_data = getattr(context.order, "client_address", None)
    if not isinstance(address_data, dict):
        return ""
    
    address_lines = []
    street = address_data.get("street_address")
    if isinstance(street, str) and street:
        return str(street)
    postal_code = address_data.get("postal_code")
    if isinstance(postal_code, str) and postal_code:
        address_lines.append(postal_code)
    state = address_data.get("state")
    if isinstance(state, str) and state:
        address_lines.append(state)
    city = address_data.get("city")
    if isinstance(city, str) and city:
        address_lines.append(city)
    country = address_data.get("country")
    if isinstance(country, str) and country:
        address_lines.append(country)
    
    return ", ".join(address_lines)



LABEL_RESOLVER_REGISTRY: dict[str, LabelResolver] = {
    "client_first_name": _resolve_client_first_name,
    "client_last_name": _resolve_client_last_name,
    "tracking_number": _resolve_tracking_number,
    "tracking_link": _resolve_tracking_link,
    "client_form_link": _resolve_client_form_link,

    "expected_arrival_time_costumer": _resolve_expected_arrival_time_costumer,
    "expected_arrival_time": _resolve_expected_arrival_time,
    "client_phone_number": _resolve_client_phone_number,
    "client_phone_number_secondary": lambda context, channel: _resolve_client_phone_number(context, channel, is_secondary=True),
    "client_address": _resolve_client_address,
    "plan_delivery_date_display": _resolve_plan_delivery_date_display,
    "reschedule_time": _resolve_reschedule_time,
}




def resolve_label(label_key: str, context: MessageRenderContext, channel: str) -> str:
    resolver = LABEL_RESOLVER_REGISTRY.get(label_key)
    if resolver is None:
        return ""
    return _to_string(resolver(context, channel))
