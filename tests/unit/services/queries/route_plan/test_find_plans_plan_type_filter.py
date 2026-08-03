from __future__ import annotations

import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.queries.route_plan.find_plans import _normalize_plan_types


def test_a_single_plan_type_is_accepted():
    assert _normalize_plan_types("international_shipping") == ["international_shipping"]


def test_a_list_of_plan_types_is_accepted():
    assert _normalize_plan_types(["local_delivery", "store_pickup"]) == [
        "local_delivery",
        "store_pickup",
    ]


def test_duplicates_and_whitespace_are_collapsed():
    assert _normalize_plan_types([" local_delivery ", "local_delivery"]) == [
        "local_delivery"
    ]


def test_an_unknown_plan_type_is_rejected():
    # A typo would otherwise be indistinguishable from "no plans of that type".
    with pytest.raises(ValidationFailed) as exc:
        _normalize_plan_types("local-delivery")

    assert "Invalid plan_type" in str(exc.value)


def test_an_unknown_entry_inside_a_list_is_rejected():
    with pytest.raises(ValidationFailed):
        _normalize_plan_types(["local_delivery", "air_freight"])


def test_a_non_string_is_rejected():
    with pytest.raises(ValidationFailed):
        _normalize_plan_types([1])


@pytest.mark.parametrize("value", ["", "   ", [], ["  "]])
def test_an_empty_filter_is_rejected(value):
    with pytest.raises(ValidationFailed):
        _normalize_plan_types(value)
