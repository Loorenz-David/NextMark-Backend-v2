from types import SimpleNamespace

from Delivery_app_BK.services.commands.order.create_order import _build_order_creation_events
from Delivery_app_BK.services.domain.order.order_events import OrderEvent


def test_order_creation_emits_created_and_client_form_submitted_events():
    order = SimpleNamespace(
        id=42,
        team_id=7,
        order_state_id=1,
        order_plan_objective="local_delivery",
        delivery_plan_id=None,
    )

    events = _build_order_creation_events(order)

    assert [event["event_name"] for event in events] == [
        OrderEvent.CREATED.value,
        OrderEvent.CLIENT_FORM_SUBMITTED.value,
    ]
    assert events[1]["payload"] == {}
