import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.requests.route_plan.plan.create_route_group import (
    parse_create_route_group_request,
)


def test_parse_create_route_group_request_accepts_zone_id_and_defaults():
    payload = {
        "zone_id": 7,
        "route_group_defaults": {
            "client_id": "rg_custom",
            "route_solution": {"set_start_time": "08:30"},
        },
    }

    result = parse_create_route_group_request(payload, route_plan_id=42)

    assert result.route_plan_id == 42
    assert result.zone_id == 7
    assert result.route_group_defaults["client_id"] == "rg_custom"


def test_parse_create_route_group_request_maps_top_level_name_alias():
    result = parse_create_route_group_request(
        {
            "name": "Overflow Bucket",
            "route_group_defaults": {},
        },
        route_plan_id=12,
    )

    assert result.zone_id is None
    assert result.route_group_defaults["name"] == "Overflow Bucket"


def test_parse_create_route_group_request_rejects_invalid_zone_id():
    with pytest.raises(ValidationFailed, match="zone_id must be greater than 0"):
        parse_create_route_group_request({"zone_id": 0}, route_plan_id=7)


def test_parse_create_route_group_request_rejects_invalid_name_alias():
    with pytest.raises(ValidationFailed, match="name must be a non-empty string"):
        parse_create_route_group_request({"name": "   "}, route_plan_id=7)
