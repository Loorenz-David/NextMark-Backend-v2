from types import SimpleNamespace

from Delivery_app_BK.services.infra.events.handlers.order import order_shopify as module


def _event(changed_sections):
    return SimpleNamespace(
        order_id=3,
        event_name="order_edited",
        payload={"changed_sections": changed_sections},
        order=SimpleNamespace(id=3),
    )


def _capture(monkeypatch):
    enqueued: list = []
    monkeypatch.setattr(module, "_enqueue_shopify_costumer_sync", enqueued.append)
    return enqueued


def test_staff_customer_edit_pushes_to_shopify(monkeypatch):
    enqueued = _capture(monkeypatch)
    event = _event(["details", "customer"])

    module.sync_shopify_costumer_on_customer_edit(event)

    assert enqueued == [event]


def test_shopify_inbound_sync_edit_does_not_echo_back(monkeypatch):
    enqueued = _capture(monkeypatch)

    module.sync_shopify_costumer_on_customer_edit(_event(["shopify_customer_sync"]))

    assert enqueued == []


def test_client_form_edit_leaves_the_push_to_the_submission_event(monkeypatch):
    enqueued = _capture(monkeypatch)

    module.sync_shopify_costumer_on_customer_edit(_event(["client_form_submission"]))

    assert enqueued == []
