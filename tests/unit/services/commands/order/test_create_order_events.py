from types import SimpleNamespace

import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.commands.order.create_order import _build_order_creation_events
from Delivery_app_BK.services.domain.order.order_events import OrderEvent
from Delivery_app_BK.services.requests.order.create_order import parse_create_order_request


def _order():
    return SimpleNamespace(
        id=42,
        team_id=7,
        order_state_id=1,
        order_plan_objective="local_delivery",
        delivery_plan_id=None,
    )


def test_staff_created_order_emits_only_created_event():
    events = _build_order_creation_events(_order())

    assert [event["event_name"] for event in events] == [OrderEvent.CREATED.value]


def test_order_created_with_linked_device_form_adds_customer_submission():
    events = _build_order_creation_events(
        _order(),
        submission_source="linked_device",
        relayed_by_user_id=5,
    )

    assert [event["event_name"] for event in events] == [
        OrderEvent.CREATED.value,
        OrderEvent.CLIENT_FORM_SUBMITTED.value,
    ]
    # The staff member created the order; the submission is the customer's.
    assert "actor_id" not in events[0]
    assert events[1]["actor_id"] is None
    assert events[1]["payload"] == {
        "submission_source": "linked_device",
        "relayed_by_user_id": 5,
    }


def test_create_request_rejects_unknown_submission_source():
    with pytest.raises(ValidationFailed):
        parse_create_order_request({"submission_source": "public_form"})


def test_create_request_carries_submission_source():
    request = parse_create_order_request({"submission_source": "linked_device"})

    assert request.submission_source == "linked_device"
    assert "submission_source" not in request.fields
