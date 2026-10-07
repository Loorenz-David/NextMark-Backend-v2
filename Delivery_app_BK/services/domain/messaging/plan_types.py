"""
Plan-type axis for message templates.

A template is scoped to the planning domain an order belongs to, so a store
pickup customer and a local delivery customer can receive different wording
for the same business event, or no message at all. The vocabulary is the
order domain's plan objectives; this module only adds the messaging-side
resolution rules.
"""

from __future__ import annotations

from typing import Any

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.domain.order.plan_objective_labels import (
    DEFAULT_ROUTE_PLAN_ORDER_OBJECTIVE,
    ORDER_PLAN_OBJECTIVES,
    normalize_order_plan_objective,
)

MESSAGE_PLAN_TYPES: frozenset[str] = frozenset(ORDER_PLAN_OBJECTIVES)
DEFAULT_MESSAGE_PLAN_TYPE: str = DEFAULT_ROUTE_PLAN_ORDER_OBJECTIVE


def validate_message_plan_type(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationFailed(
            f"Invalid plan_type '{value}'. Allowed values: {sorted(MESSAGE_PLAN_TYPES)}"
        )

    normalized = normalize_order_plan_objective(value.strip())
    if normalized not in MESSAGE_PLAN_TYPES:
        raise ValidationFailed(
            f"Invalid plan_type '{value}'. Allowed values: {sorted(MESSAGE_PLAN_TYPES)}"
        )
    return normalized


def _normalize_known(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = normalize_order_plan_objective(value.strip())
    if normalized in MESSAGE_PLAN_TYPES:
        return normalized
    return None


def resolve_order_message_plan_type(order: Any) -> str:
    """
    The plan owns the objective: an assigned order answers with its plan's type.
    The order's own copy is only consulted when no plan is assigned (e.g. an
    order created straight into a pickup intent), and local delivery is the
    last resort so legacy rows without either still resolve.
    """
    if order is None:
        return DEFAULT_MESSAGE_PLAN_TYPE

    route_plan = getattr(order, "route_plan", None)
    from_plan = _normalize_known(getattr(route_plan, "plan_type", None))
    if from_plan is not None:
        return from_plan

    from_order = _normalize_known(getattr(order, "order_plan_objective", None))
    if from_order is not None:
        return from_order

    return DEFAULT_MESSAGE_PLAN_TYPE


def should_message_order_customer(order: Any) -> bool:
    """
    An order with neither a plan nor an objective (e.g. a Shopify order the
    customer took at the counter) has no planning domain to speak for, so no
    automatic customer message applies to it.
    """
    if order is None:
        return True
    if getattr(order, "route_plan", None) is not None:
        return True
    return getattr(order, "order_plan_objective", None) is not None


def resolve_route_plan_message_plan_type(route_plan: Any) -> str:
    from_plan = _normalize_known(getattr(route_plan, "plan_type", None))
    if from_plan is not None:
        return from_plan
    return DEFAULT_MESSAGE_PLAN_TYPE
