"""Parsing for the fields every route plan carries, whatever domain owns it.

A route plan is a neutral container: a label, a date window, and the orders that
belong to it. Each planning domain layers its own fields on top and validates
those itself, so this module never learns about carriers, pickup locations, or
route groups.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import RoutePlan
from Delivery_app_BK.services.requests.common.datetime import (
    default_end_date,
    normalize_end_date,
    normalize_start_date,
)
from Delivery_app_BK.services.requests.common.types import (
    parse_client_id,
    validate_int_list,
    validate_str,
)


PLAN_SHELL_FIELDS = {
    "client_id",
    "label",
    "date_strategy",
    "start_date",
    "end_date",
    "order_ids",
}

REQUIRED_PLAN_SHELL_FIELDS = {
    "label",
    "start_date",
}


@dataclass
class PlanShell:
    client_id: str
    label: str
    date_strategy: str
    start_date: datetime
    end_date: datetime
    order_ids: list[int]


def parse_plan_shell(raw_fields: dict, *, client_id_prefix: str) -> PlanShell:
    client_id = parse_client_id(raw_fields.get("client_id"), prefix=client_id_prefix)
    label = validate_str(raw_fields.get("label"), field="label")

    date_strategy = validate_str(
        raw_fields.get("date_strategy", "single"),
        field="date_strategy",
    )
    if date_strategy not in RoutePlan.DATE_STRATEGIES:
        raise ValidationFailed(f"Invalid date_strategy: {date_strategy}")

    start_date = normalize_start_date(raw_fields.get("start_date"))
    raw_end_date = raw_fields.get("end_date")
    end_date = (
        default_end_date(start_date)
        if raw_end_date is None
        else normalize_end_date(raw_end_date)
    )
    if end_date < start_date:
        raise ValidationFailed("end_date cannot be before start_date.")

    return PlanShell(
        client_id=client_id,
        label=label,
        date_strategy=date_strategy,
        start_date=start_date,
        end_date=end_date,
        order_ids=validate_int_list(raw_fields.get("order_ids"), field="order_ids"),
    )
