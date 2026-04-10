from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.requests.common.datetime import parse_optional_datetime
from Delivery_app_BK.services.requests.common.fields import validate_unexpected

ALLOWED_FIELDS = {"observed_time"}


@dataclass
class DriverObservedTimeRequest:
    observed_time: datetime | None = None


def parse_driver_observed_time_request(raw: dict | None) -> DriverObservedTimeRequest:
    if raw is None:
        return DriverObservedTimeRequest()
    if not isinstance(raw, dict):
        raise ValidationFailed("Payload must be an object.")

    validate_unexpected(
        raw,
        ALLOWED_FIELDS,
        context_msg="Unexpected fields in driver timing payload:",
    )

    if "observed_time" not in raw or raw.get("observed_time") is None:
        return DriverObservedTimeRequest()

    return DriverObservedTimeRequest(
        observed_time=parse_optional_datetime(raw.get("observed_time"), field="observed_time"),
    )
