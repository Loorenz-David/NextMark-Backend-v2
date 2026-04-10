import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.requests.order.create_order import parse_create_order_request


def test_parse_create_order_accepts_nested_costumer_payload():
    parsed = parse_create_order_request(
        {
            "client_id": "order_1",
            "costumer": {
                "costumer_id": 22,
                "client_id": "costumer_22",
                "email": "martha@mail.com",
            },
            "client_first_name": "Martha",
        }
    )

    assert parsed.costumer is not None
    assert parsed.costumer.costumer_id == 22
    assert parsed.costumer.client_id == "costumer_22"
    assert parsed.costumer.email == "martha@mail.com"
    assert parsed.fields["client_id"] == "order_1"


def test_parse_create_order_rejects_non_object_costumer():
    with pytest.raises(ValidationFailed):
        parse_create_order_request({"costumer": "not-an-object"})


def test_parse_create_order_rejects_string_nested_costumer_id():
    with pytest.raises(ValidationFailed):
        parse_create_order_request({"costumer": {"costumer_id": "22"}})


def test_parse_create_order_rejects_bool_nested_costumer_id():
    with pytest.raises(ValidationFailed):
        parse_create_order_request({"costumer": {"costumer_id": True}})


def test_parse_create_order_preserves_existing_fields_behavior():
    parsed = parse_create_order_request(
        {
            "route_plan_id": 3,
            "route_group_id": 11,
            "reference_number": "REF-1",
            "order_state_id": 2,
        }
    )

    assert parsed.route_plan_id == 3
    assert parsed.route_group_id == 11
    assert parsed.costumer is None
    assert parsed.fields["route_plan_id"] == 3
    assert parsed.fields["route_group_id"] == 11
    assert parsed.fields["reference_number"] == "REF-1"
    assert parsed.fields["order_state_id"] == 2


def test_parse_create_order_accepts_route_plan_id_alias():
    parsed = parse_create_order_request(
        {
            "route_plan_id": 7,
            "route_group_id": 71,
            "reference_number": "REF-2",
        }
    )

    assert parsed.route_plan_id == 7
    assert parsed.route_group_id == 71
    assert parsed.fields["route_plan_id"] == 7
    assert parsed.fields["route_group_id"] == 71


def test_parse_create_order_requires_route_group_when_route_plan_is_present():
    with pytest.raises(ValidationFailed):
        parse_create_order_request(
            {
                "route_plan_id": 3,
                "reference_number": "REF-1",
            }
        )


def test_parse_create_order_requires_route_plan_when_route_group_is_present():
    with pytest.raises(ValidationFailed):
        parse_create_order_request(
            {
                "route_group_id": 11,
                "reference_number": "REF-1",
            }
        )


def test_parse_create_order_rejects_mismatched_plan_id_aliases():
    with pytest.raises(ValidationFailed):
        parse_create_order_request(
            {
                "route_plan_id": 7,
                "delivery_plan_id": 8,
            }
        )


def test_parse_create_order_rejects_legacy_delivery_plan_id_input_alias():
    with pytest.raises(ValidationFailed):
        parse_create_order_request(
            {
                "route_plan_id": 9,
                "delivery_plan_id": 9,
            }
        )


def test_parse_create_order_normalizes_route_operations_objective_alias():
    parsed = parse_create_order_request(
        {
            "order_plan_objective": "route_operations",
        }
    )

    assert parsed.fields["order_plan_objective"] == "local_delivery"


def test_parse_create_order_preserves_delivery_windows_payload():
    parsed = parse_create_order_request(
        {
            "client_id": "order_1",
            "delivery_windows": [
                {
                    "client_id": "dw_1",
                    "start_at": "2026-03-05T09:00:00+00:00",
                    "end_at": "2026-03-05T11:00:00+00:00",
                    "window_type": "FULL_RANGE",
                }
            ],
        },
    )

    assert parsed.delivery_windows is not None
    assert parsed.delivery_windows[0]["client_id"] == "dw_1"
    assert parsed.delivery_windows[0]["window_type"] == "FULL_RANGE"


def test_parse_create_order_delivery_windows_null_means_explicit_clear():
    parsed = parse_create_order_request({"delivery_windows": None})
    assert parsed.delivery_windows == []


def test_parse_create_order_normalizes_general_order_note_and_injects_creation_date():
    parsed = parse_create_order_request(
        {
            "order_notes": {
                "type": "GENERAL",
            }
        }
    )

    notes = parsed.fields["order_notes"]
    assert isinstance(notes, list)
    assert len(notes) == 1
    assert notes[0]["type"] == "GENERAL"
    assert notes[0]["content"] == ""
    assert isinstance(notes[0]["creation_date"], str)


def test_parse_create_order_rejects_non_general_order_note_type():
    with pytest.raises(ValidationFailed):
        parse_create_order_request(
            {
                "order_notes": {
                    "type": "FAILURE",
                    "content": "x",
                }
            }
        )
