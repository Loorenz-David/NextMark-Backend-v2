import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.commands.order.update_order import (
    _validate_targets_update_fields,
)


def test_validate_targets_allows_mutable_fields():
    targets = [
        {
            "target_id": 10,
            "fields": {
                "client_first_name": "Ana",
                "delivery_windows": [],
            },
        }
    ]

    _validate_targets_update_fields(targets)


def test_validate_targets_rejects_forbidden_state_change_fields():
    targets = [
        {
            "target_id": 10,
            "fields": {"order_state_id": 2},
        }
    ]

    with pytest.raises(ValidationFailed):
        _validate_targets_update_fields(targets)


def test_validate_targets_rejects_forbidden_route_plan_field():
    targets = [
        {
            "target_id": 10,
            "fields": {"route_plan_id": 2},
        }
    ]

    with pytest.raises(ValidationFailed):
        _validate_targets_update_fields(targets)


def test_validate_targets_rejects_forbidden_delivery_plan_relationship():
    targets = [
        {
            "target_id": 10,
            "fields": {"delivery_plan": 8},
        }
    ]

    with pytest.raises(ValidationFailed):
        _validate_targets_update_fields(targets)


def test_validate_targets_rejects_unsupported_fields():
    targets = [
        {
            "target_id": 10,
            "fields": {"unknown_field": "value"},
        }
    ]

    with pytest.raises(ValidationFailed):
        _validate_targets_update_fields(targets)
