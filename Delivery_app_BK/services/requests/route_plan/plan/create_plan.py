from dataclasses import dataclass
from datetime import datetime

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import RoutePlan
from Delivery_app_BK.services.requests.common.datetime import (
    default_end_date,
    normalize_end_date,
    normalize_start_date,
)
from Delivery_app_BK.services.requests.common.fields import (
    validate_forbidden,
    validate_required,
    validate_unexpected,
)
from Delivery_app_BK.services.requests.common.types import (
    parse_client_id,
    validate_int_list,
    validate_str,
)


ALLOWED_CREATE_FIELDS = {
    "client_id",
    "label",
    "date_strategy",
    "start_date",
    "end_date",
    "order_ids",
    "zone_ids",
    "route_group_defaults",
}

LEGACY_REJECTED_FIELDS = {
    "local_delivery",
    "international_shipping",
    "store_pickup",
    "new_order_links",
}

REQUIRED_CREATE_FIELDS = {
    "label",
    "start_date",
}


@dataclass
class PlanCreateRequest:
    client_id: str
    label: str
    date_strategy: str
    start_date: datetime
    end_date: datetime
    order_ids: list[int]
    zone_ids: list[int]
    route_group_defaults: dict


def _normalize_route_group_defaults(raw_defaults: object) -> dict:
    if raw_defaults is None:
        return {}
    if not isinstance(raw_defaults, dict):
        raise ValidationFailed("route_group_defaults must be an object.")
    return raw_defaults


def _normalize_zone_ids(raw_zone_ids: object) -> list[int]:
    zone_ids = validate_int_list(raw_zone_ids, field="zone_ids")
    for index, zone_id in enumerate(zone_ids):
        if zone_id <= 0:
            raise ValidationFailed(f"zone_ids[{index}] must be greater than 0")
    return zone_ids


def parse_create_plan_request(raw_fields: dict) -> PlanCreateRequest:
    if not isinstance(raw_fields, dict):
        raise ValidationFailed("Each create payload in 'fields' must be an object.")

    if "state_id" in raw_fields:
        raise ValidationFailed(
            "state_id is not allowed on create. New plans always start as OPEN."
        )

    validate_forbidden(
        raw_fields,
        LEGACY_REJECTED_FIELDS,
        context_msg="Legacy create fields are no longer allowed:",
    )
    validate_unexpected(
        raw_fields,
        ALLOWED_CREATE_FIELDS,
        context_msg="Unexpected fields in create payload:",
    )
    validate_required(
        raw_fields,
        REQUIRED_CREATE_FIELDS,
        context_msg="Missing required fields for create plan.",
    )

    client_id = parse_client_id(raw_fields.get("client_id"), prefix="delivery_plan")
    label = validate_str(raw_fields.get("label"), field="label")
    date_strategy = raw_fields.get("date_strategy", "single")
    date_strategy = validate_str(date_strategy, field="date_strategy")
    if date_strategy not in RoutePlan.DATE_STRATEGIES:
        raise ValidationFailed(f"Invalid date_strategy: {date_strategy}")

    start_date = normalize_start_date(raw_fields.get("start_date"))
    raw_end_date = raw_fields.get("end_date")
    end_date = default_end_date(start_date) if raw_end_date is None else normalize_end_date(
        raw_end_date
    )
    if end_date < start_date:
        raise ValidationFailed("end_date cannot be before start_date.")

    order_ids = validate_int_list(raw_fields.get("order_ids"), field="order_ids")
    zone_ids = _normalize_zone_ids(raw_fields.get("zone_ids"))
    route_group_defaults = _normalize_route_group_defaults(
        raw_fields.get("route_group_defaults")
    )

    return PlanCreateRequest(
        client_id=client_id,
        label=label,
        date_strategy=date_strategy,
        start_date=start_date,
        end_date=end_date,
        order_ids=order_ids,
        zone_ids=zone_ids,
        route_group_defaults=route_group_defaults,
    )
