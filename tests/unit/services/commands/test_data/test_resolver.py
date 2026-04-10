import pytest

from Delivery_app_BK.services.commands.test_data.registry import (
    RefResolutionError,
    Registry,
)
from Delivery_app_BK.services.commands.test_data.resolver import resolve_item


def test_strips_dollar_id():
    registry = Registry()

    result = resolve_item("facility", {"$id": "f1", "name": "Depot"}, registry)

    assert result == {"name": "Depot"}


def test_strips_underscore_keys():
    registry = Registry()

    result = resolve_item(
        "route_plan",
        {"label": "Plan", "_sid": "p1", "_zone_sids": ["z1"]},
        registry,
    )

    assert result == {"label": "Plan"}


def test_resolves_scalar_ref():
    registry = Registry()
    registry.register("f1", 101, "facility")

    result = resolve_item("vehicle", {"$facility": "f1", "label": "Van 1"}, registry)

    assert result == {"home_facility_id": 101, "label": "Van 1"}


def test_resolves_list_ref():
    registry = Registry()
    registry.register("z1", 101, "zone")
    registry.register("z2", 102, "zone")

    result = resolve_item("route_plan", {"$zones": ["z1", "z2"]}, registry)

    assert result == {"zone_ids": [101, 102]}


def test_unknown_dollar_key_raises():
    registry = Registry()

    with pytest.raises(RefResolutionError):
        resolve_item("vehicle", {"$unknown": "f1"}, registry)


def test_unresolvable_sid_raises():
    registry = Registry()

    with pytest.raises(RefResolutionError) as exc:
        resolve_item("vehicle", {"$facility": "missing"}, registry)

    assert "vehicle" in str(exc.value)
    assert "$facility" in str(exc.value)


def test_passthrough_non_ref_keys():
    registry = Registry()

    result = resolve_item(
        "facility",
        {"name": "Depot", "can_dispatch": True, "facility_type": "warehouse"},
        registry,
    )

    assert result == {
        "name": "Depot",
        "can_dispatch": True,
        "facility_type": "warehouse",
    }


def test_entity_with_no_ref_rules():
    registry = Registry()

    result = resolve_item("item_property", {"name": "Color", "field_type": "text"}, registry)

    assert result == {"name": "Color", "field_type": "text"}
