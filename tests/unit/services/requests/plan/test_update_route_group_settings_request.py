import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.requests.route_plan.plan.local_delivery.update_settings import (
    parse_update_local_delivery_settings_request,
    parse_update_route_group_settings_request,
)


def _base_payload() -> dict:
    return {
        "route_group_id": 10,
        "route_plan": {
            "label": "Morning routes",
        },
        "route_group": {},
        "route_solution": {
            "route_solution_id": 900,
            "driver_id": 22,
        },
    }


def test_parse_update_local_delivery_settings_request_accepts_canonical_keys():
    parsed = parse_update_local_delivery_settings_request(_base_payload())

    assert parsed.route_group_id == 10
    assert parsed.route_plan.label == "Morning routes"
    assert parsed.route_solution.route_solution_id == 900
    assert parsed.route_solution.driver_id == 22


def test_parse_update_local_delivery_settings_request_accepts_eta_message_tolerance_seconds():
    payload = _base_payload()
    payload["route_solution"]["eta_message_tolerance"] = 2400

    parsed = parse_update_local_delivery_settings_request(payload)

    assert parsed.route_solution.has_eta_message_tolerance is True
    assert parsed.route_solution.eta_message_tolerance == 2400


def test_parse_update_local_delivery_settings_request_rejects_invalid_eta_message_tolerance():
    payload = _base_payload()
    payload["route_solution"]["eta_message_tolerance"] = "2400"

    with pytest.raises(ValidationFailed):
        parse_update_local_delivery_settings_request(payload)


def test_parse_update_local_delivery_settings_request_rejects_legacy_top_level_keys():
    payload = _base_payload()
    payload["delivery_plan"] = {"label": "Legacy"}

    with pytest.raises(ValidationFailed):
        parse_update_local_delivery_settings_request(payload)


def test_parse_update_route_group_settings_request_rejects_legacy_local_delivery_key():
    payload = _base_payload()
    payload["local_delivery_plan"] = {"driver_id": 22}

    with pytest.raises(ValidationFailed):
        parse_update_route_group_settings_request(payload)


def test_parse_update_local_delivery_settings_request_rejects_route_group_driver_field():
    payload = _base_payload()
    payload["route_group"] = {"driver_id": 22}

    with pytest.raises(ValidationFailed):
        parse_update_local_delivery_settings_request(payload)
