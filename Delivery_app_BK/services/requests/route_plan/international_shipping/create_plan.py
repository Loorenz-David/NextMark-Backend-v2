from __future__ import annotations

from dataclasses import dataclass

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.requests.common.fields import (
    validate_required,
    validate_unexpected,
)
from Delivery_app_BK.services.requests.common.types import validate_str
from Delivery_app_BK.services.requests.route_plan.common.plan_shell import (
    PLAN_SHELL_FIELDS,
    REQUIRED_PLAN_SHELL_FIELDS,
    PlanShell,
    parse_plan_shell,
)


DOMAIN_FIELDS = {"carrier_name"}

ALLOWED_CREATE_FIELDS = PLAN_SHELL_FIELDS | DOMAIN_FIELDS

# Route groups and zones are route-operations concepts. Naming them explicitly
# gives a caller who copies a local-delivery payload a useful error instead of a
# generic "unexpected field".
ROUTE_OPERATIONS_FIELDS = {"zone_ids", "route_group_defaults", "route_group_id"}


@dataclass
class InternationalShippingPlanCreateRequest:
    shell: PlanShell
    carrier_name: str | None


def parse_create_international_shipping_plan_request(
    raw_fields: dict,
) -> InternationalShippingPlanCreateRequest:
    if not isinstance(raw_fields, dict):
        raise ValidationFailed("Each create payload in 'fields' must be an object.")

    if "state_id" in raw_fields:
        raise ValidationFailed(
            "state_id is not allowed on create. New plans always start as OPEN."
        )
    if "plan_type" in raw_fields:
        raise ValidationFailed(
            "plan_type is implied by this endpoint and cannot be set on the payload."
        )

    found_route_operations = sorted(
        key for key in ROUTE_OPERATIONS_FIELDS if key in raw_fields
    )
    if found_route_operations:
        raise ValidationFailed(
            "International shipping plans do not have route groups or zones. "
            f"Unsupported fields: {found_route_operations}."
        )

    validate_unexpected(
        raw_fields,
        ALLOWED_CREATE_FIELDS,
        context_msg="Unexpected fields in create payload:",
    )
    validate_required(
        raw_fields,
        REQUIRED_PLAN_SHELL_FIELDS,
        context_msg="Missing required fields for create international shipping plan.",
    )

    raw_carrier_name = raw_fields.get("carrier_name")
    carrier_name = (
        None
        if raw_carrier_name is None
        else validate_str(raw_carrier_name, field="carrier_name")
    )

    return InternationalShippingPlanCreateRequest(
        shell=parse_plan_shell(raw_fields, client_id_prefix="international_shipping_plan"),
        carrier_name=carrier_name,
    )
