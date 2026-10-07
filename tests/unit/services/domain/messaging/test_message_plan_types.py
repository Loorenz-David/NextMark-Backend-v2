from types import SimpleNamespace

import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models.tables.order.order import Order
from Delivery_app_BK.models.tables.route_operations.route_plan.route_plan import RoutePlan
from Delivery_app_BK.services.domain.messaging import (
    DEFAULT_MESSAGE_PLAN_TYPE,
    MESSAGE_PLAN_TYPES,
    resolve_order_message_plan_type,
    resolve_route_plan_message_plan_type,
    should_message_order_customer,
    validate_message_plan_type,
)


def test_message_plan_types_match_every_other_copy_of_the_vocabulary():
    # The strings are duplicated across domains; messaging must not drift.
    assert MESSAGE_PLAN_TYPES == frozenset(RoutePlan.PLAN_TYPES)
    assert MESSAGE_PLAN_TYPES == frozenset(Order.ORDER_PLAN_INTENTIONS)
    assert DEFAULT_MESSAGE_PLAN_TYPE == "local_delivery"


def test_order_plan_type_comes_from_the_assigned_plan_first():
    order = SimpleNamespace(
        route_plan=SimpleNamespace(plan_type="store_pickup"),
        order_plan_objective="local_delivery",
    )

    assert resolve_order_message_plan_type(order) == "store_pickup"


def test_order_plan_type_falls_back_to_the_order_objective_without_a_plan():
    order = SimpleNamespace(route_plan=None, order_plan_objective="international_shipping")

    assert resolve_order_message_plan_type(order) == "international_shipping"


def test_order_plan_type_normalizes_legacy_aliases():
    order = SimpleNamespace(route_plan=None, order_plan_objective="route_operations")

    assert resolve_order_message_plan_type(order) == "local_delivery"


@pytest.mark.parametrize(
    "order",
    [
        None,
        SimpleNamespace(route_plan=None, order_plan_objective=None),
        SimpleNamespace(route_plan=None, order_plan_objective="unknown"),
        SimpleNamespace(route_plan=SimpleNamespace(plan_type="bogus"), order_plan_objective=None),
    ],
)
def test_order_plan_type_defaults_to_local_delivery(order):
    assert resolve_order_message_plan_type(order) == "local_delivery"


@pytest.mark.parametrize("plan_type", sorted(MESSAGE_PLAN_TYPES))
def test_route_plan_plan_type_is_read_from_the_plan(plan_type):
    assert resolve_route_plan_message_plan_type(SimpleNamespace(plan_type=plan_type)) == plan_type


def test_route_plan_plan_type_defaults_without_a_plan():
    assert resolve_route_plan_message_plan_type(None) == "local_delivery"


@pytest.mark.parametrize("plan_type", sorted(MESSAGE_PLAN_TYPES))
def test_validate_accepts_every_plan_type_and_strips_whitespace(plan_type):
    assert validate_message_plan_type(f"  {plan_type} ") == plan_type


def test_validate_normalizes_legacy_aliases():
    assert validate_message_plan_type("route_operation") == "local_delivery"


@pytest.mark.parametrize("value", ["", "   ", None, "pickup", 7])
def test_validate_rejects_unknown_values(value):
    with pytest.raises(ValidationFailed, match="Invalid plan_type"):
        validate_message_plan_type(value)


def test_order_without_plan_or_objective_is_not_messaged():
    order = SimpleNamespace(route_plan=None, order_plan_objective=None)

    assert should_message_order_customer(order) is False


@pytest.mark.parametrize(
    "order",
    [
        SimpleNamespace(route_plan=None, order_plan_objective="store_pickup"),
        SimpleNamespace(route_plan=SimpleNamespace(plan_type="local_delivery"), order_plan_objective=None),
        None,
    ],
)
def test_order_with_plan_or_objective_is_messaged(order):
    assert should_message_order_customer(order) is True
