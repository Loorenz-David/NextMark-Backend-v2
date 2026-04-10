from __future__ import annotations

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.domain.order.order_events import OrderEvent
from Delivery_app_BK.services.domain.route_operations.plan.plan_events import RoutePlanEvent

SCHEDULE_ANCHOR_OCCURRED_AT = "event_occurred_at"
SCHEDULE_ANCHOR_FUTURE_BUSINESS_TIME = "future_business_time"

SCHEDULE_OFFSET_UNIT_MINUTES = "minutes"
SCHEDULE_OFFSET_UNIT_HOURS = "hours"
SCHEDULE_OFFSET_UNIT_DAYS = "days"

ALLOWED_SCHEDULE_OFFSET_UNITS = {
    SCHEDULE_OFFSET_UNIT_MINUTES,
    SCHEDULE_OFFSET_UNIT_HOURS,
    SCHEDULE_OFFSET_UNIT_DAYS,
}

MAX_ABSOLUTE_OFFSET_BY_UNIT = {
    SCHEDULE_OFFSET_UNIT_MINUTES: 60 * 24 * 365,
    SCHEDULE_OFFSET_UNIT_HOURS: 24 * 365,
    SCHEDULE_OFFSET_UNIT_DAYS: 365,
}

FUTURE_ANCHOR_EVENTS = {
    OrderEvent.DELIVERY_WINDOW_RESCHEDULED_BY_USER.value,
    OrderEvent.DELIVERY_PLAN_CHANGED.value,
    OrderEvent.DELIVERY_RESCHEDULED.value,
    RoutePlanEvent.DELIVERY_PLAN_RESCHEDULED.value,
}


def event_supports_future_anchor(event_name: str | None) -> bool:
    return bool(event_name and event_name in FUTURE_ANCHOR_EVENTS)


def validate_schedule_configuration(
    *,
    event_name: str | None,
    offset_value: int | None,
    offset_unit: str | None,
) -> None:
    if offset_value is None and offset_unit is None:
        return

    if offset_value is None or offset_unit is None:
        raise ValidationFailed(
            "Both schedule_offset_value and schedule_offset_unit must be provided together.",
        )

    if not isinstance(offset_value, int) or isinstance(offset_value, bool):
        raise ValidationFailed("schedule_offset_value must be an integer.")

    if offset_unit not in ALLOWED_SCHEDULE_OFFSET_UNITS:
        raise ValidationFailed(
            f"schedule_offset_unit must be one of {sorted(ALLOWED_SCHEDULE_OFFSET_UNITS)}.",
        )

    max_absolute_value = MAX_ABSOLUTE_OFFSET_BY_UNIT[offset_unit]
    if abs(offset_value) > max_absolute_value:
        raise ValidationFailed(
            f"schedule_offset_value is out of range for unit '{offset_unit}'.",
        )

    if offset_value < 0 and not event_supports_future_anchor(event_name):
        raise ValidationFailed(
            "Negative schedule offsets are only allowed for events with a future business anchor.",
        )
