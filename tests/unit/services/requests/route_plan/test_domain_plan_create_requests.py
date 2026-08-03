from __future__ import annotations

import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.requests.route_plan.international_shipping.create_plan import (
    parse_create_international_shipping_plan_request,
)
from Delivery_app_BK.services.requests.route_plan.store_pickup.create_plan import (
    parse_create_store_pickup_plan_request,
)


def _base():
    return {"label": "Q3 Overseas", "start_date": "2026-09-01"}


# --- international shipping -------------------------------------------------


def test_international_shipping_parses_its_own_field():
    parsed = parse_create_international_shipping_plan_request(
        {**_base(), "carrier_name": "DHL Express", "order_ids": [1, 2]}
    )

    assert parsed.carrier_name == "DHL Express"
    assert parsed.shell.label == "Q3 Overseas"
    assert parsed.shell.order_ids == [1, 2]
    assert parsed.shell.client_id.startswith("international_shipping_plan")


def test_international_shipping_carrier_name_is_optional():
    assert parse_create_international_shipping_plan_request(_base()).carrier_name is None


@pytest.mark.parametrize(
    "route_ops_field",
    ["zone_ids", "route_group_defaults", "route_group_id"],
)
def test_international_shipping_rejects_route_operations_fields(route_ops_field):
    # A caller copying a local-delivery payload should be told why, not get a
    # generic "unexpected field".
    with pytest.raises(ValidationFailed) as exc:
        parse_create_international_shipping_plan_request(
            {**_base(), route_ops_field: [1]}
        )

    assert "route groups" in str(exc.value)


def test_plan_type_cannot_be_set_on_the_payload():
    with pytest.raises(ValidationFailed):
        parse_create_international_shipping_plan_request(
            {**_base(), "plan_type": "local_delivery"}
        )


def test_state_id_is_rejected_on_create():
    with pytest.raises(ValidationFailed):
        parse_create_international_shipping_plan_request({**_base(), "state_id": 2})


def test_missing_required_shell_fields_are_reported():
    with pytest.raises(ValidationFailed):
        parse_create_international_shipping_plan_request({"label": "no start date"})


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationFailed):
        parse_create_international_shipping_plan_request({**_base(), "nonsense": 1})


# --- store pickup -----------------------------------------------------------


def test_store_pickup_parses_its_own_fields():
    location = {
        "street_address": "123 Main St",
        "country": "CO",
        "coordinates": {"lat": 4.6, "lng": -74.1},
    }
    parsed = parse_create_store_pickup_plan_request(
        {**_base(), "pickup_location": location, "assigned_user_id": 7}
    )

    assert parsed.pickup_location == location
    assert parsed.assigned_user_id == 7
    assert parsed.shell.client_id.startswith("store_pickup_plan")


def test_store_pickup_domain_fields_are_optional():
    parsed = parse_create_store_pickup_plan_request(_base())

    assert parsed.pickup_location is None
    assert parsed.assigned_user_id is None


def test_store_pickup_location_must_be_an_object():
    with pytest.raises(ValidationFailed):
        parse_create_store_pickup_plan_request(
            {**_base(), "pickup_location": "123 Main St"}
        )


def test_store_pickup_assigned_user_id_must_be_an_integer():
    with pytest.raises(ValidationFailed):
        parse_create_store_pickup_plan_request({**_base(), "assigned_user_id": "7"})


@pytest.mark.parametrize(
    "route_ops_field",
    ["zone_ids", "route_group_defaults", "route_group_id"],
)
def test_store_pickup_rejects_route_operations_fields(route_ops_field):
    with pytest.raises(ValidationFailed) as exc:
        parse_create_store_pickup_plan_request({**_base(), route_ops_field: [1]})

    assert "route groups" in str(exc.value)


def test_end_date_before_start_date_is_rejected():
    with pytest.raises(ValidationFailed):
        parse_create_store_pickup_plan_request(
            {"label": "Backwards", "start_date": "2026-09-10", "end_date": "2026-09-01"}
        )
