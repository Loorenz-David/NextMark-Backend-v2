from dataclasses import dataclass

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.requests.common.fields import validate_unexpected


ALLOWED_FIELDS = {
    "zone_id",
    "name",
    "route_group_defaults",
}


@dataclass
class RouteGroupCreateRequest:
    route_plan_id: int
    zone_id: int | None
    route_group_defaults: dict


def parse_create_route_group_request(raw_payload: dict, *, route_plan_id: int) -> RouteGroupCreateRequest:
    if isinstance(route_plan_id, bool) or not isinstance(route_plan_id, int) or route_plan_id <= 0:
        raise ValidationFailed("route_plan_id must be a positive integer")

    if not isinstance(raw_payload, dict):
        raise ValidationFailed("Payload must be an object.")

    validate_unexpected(
        raw_payload,
        ALLOWED_FIELDS,
        context_msg="Unexpected fields in create route group payload:",
    )

    zone_id_raw = raw_payload.get("zone_id")
    zone_id = _normalize_optional_zone_id(zone_id_raw)

    defaults = _normalize_route_group_defaults(raw_payload.get("route_group_defaults"))

    # Convenience alias: top-level "name" can populate route_group_defaults.name.
    if "name" in raw_payload:
        name_value = raw_payload.get("name")
        if name_value is None:
            defaults.pop("name", None)
        elif isinstance(name_value, str) and name_value.strip():
            defaults["name"] = name_value.strip()
        else:
            raise ValidationFailed("name must be a non-empty string.")

    return RouteGroupCreateRequest(
        route_plan_id=route_plan_id,
        zone_id=zone_id,
        route_group_defaults=defaults,
    )


def _normalize_optional_zone_id(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationFailed("zone_id must be an integer.")
    if value <= 0:
        raise ValidationFailed("zone_id must be greater than 0.")
    return value


def _normalize_route_group_defaults(value: object) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValidationFailed("route_group_defaults must be an object.")
    return dict(value)
