from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.requests.common.datetime import parse_optional_datetime
from Delivery_app_BK.services.requests.common.fields import validate_unexpected


ALLOWED_FIELDS = {"time"}


@dataclass
class ActualTimeMarkRequest:
    time: datetime | None = None


def parse_mark_actual_time_request(raw: dict | None) -> ActualTimeMarkRequest:
    if raw is None:
        return ActualTimeMarkRequest()
    if not isinstance(raw, dict):
        raise ValidationFailed("Payload must be an object.")

    validate_unexpected(
        raw,
        ALLOWED_FIELDS,
        context_msg="Unexpected fields in actual time payload:",
    )

    if "time" not in raw or raw.get("time") is None:
        return ActualTimeMarkRequest()

    return ActualTimeMarkRequest(
        time=parse_optional_datetime(raw.get("time"), field="time"),
    )
