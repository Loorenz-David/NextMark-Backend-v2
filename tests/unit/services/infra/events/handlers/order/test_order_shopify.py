from types import SimpleNamespace

from Delivery_app_BK.services.infra.events.handlers.order import order_shopify as module


def test_sync_shopify_fulfillment_on_order_completed_enqueues_job(monkeypatch):
    calls: list[dict] = []
    order = SimpleNamespace(id=18, external_source="shopify", external_order_id="12345")

    monkeypatch.setattr(module, "enqueue_job", lambda **kwargs: calls.append(kwargs))

    module.sync_shopify_fulfillment_on_order_completed(
        SimpleNamespace(order=order, order_id=18),
    )

    assert len(calls) == 1
    assert calls[0]["queue_key"] == "default"
    assert calls[0]["args"] == (18,)
    assert calls[0]["description"] == "fulfill-shopify-order:18"


def test_sync_shopify_fulfillment_on_order_completed_skips_non_shopify_orders(monkeypatch):
    calls: list[dict] = []
    order = SimpleNamespace(id=18, external_source="manual", external_order_id=None)

    monkeypatch.setattr(module, "enqueue_job", lambda **kwargs: calls.append(kwargs))

    module.sync_shopify_fulfillment_on_order_completed(
        SimpleNamespace(order=order, order_id=18),
    )

    assert calls == []
