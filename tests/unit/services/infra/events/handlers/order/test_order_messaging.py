from Delivery_app_BK.services.domain.order.order_events import OrderEvent
from Delivery_app_BK.services.infra.events.event_bus import EventBus
from Delivery_app_BK.services.infra.events.handlers.order import order_email, order_sms
from Delivery_app_BK.services.infra.events.registry.order import register_order_event_handlers


def test_client_form_submitted_email_uses_expected_action(monkeypatch):
    event = object()
    calls = []
    monkeypatch.setattr(
        order_email,
        "run_action",
        lambda received_event, action_name: calls.append((received_event, action_name)),
    )

    order_email.send_email_on_client_form_submitted(event)

    assert calls == [(event, "client_form_submitted_email")]


def test_client_form_submitted_sms_uses_expected_action(monkeypatch):
    event = object()
    calls = []
    monkeypatch.setattr(
        order_sms,
        "run_action",
        lambda received_event, action_name: calls.append((received_event, action_name)),
    )

    order_sms.send_sms_on_client_form_submitted(event)

    assert calls == [(event, "client_form_submitted_sms")]


def test_client_form_submitted_registers_independent_sms_and_email_handlers():
    event_bus = EventBus()

    register_order_event_handlers(event_bus)

    handlers = list(event_bus.get_handlers(OrderEvent.CLIENT_FORM_SUBMITTED.value))
    assert handlers == [
        order_sms.send_sms_on_client_form_submitted,
        order_email.send_email_on_client_form_submitted,
    ]
