from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.domain.route_operations.local_delivery import (
    normalize_service_time_payload,
)
from Delivery_app_BK.services.requests.common.fields import validate_unexpected


ALLOWED_FIELDS = {
    "service_time",
}


@dataclass(frozen=True)
class RouteStopServiceTimeRequest:
    service_time: dict | None


def parse_update_route_stop_service_time_request(raw: Any) -> RouteStopServiceTimeRequest:
    if not isinstance(raw, dict):
        raise ValidationFailed("Payload must be an object.")

    validate_unexpected(
        raw,
        ALLOWED_FIELDS,
        context_msg="Unexpected fields in route stop service time payload:",
    )

    if "service_time" not in raw:
        raise ValidationFailed("service_time is required.")

    return RouteStopServiceTimeRequest(
        service_time=normalize_service_time_payload(
            raw.get("service_time"),
            field="service_time",
            strict=True,
        )
    )
