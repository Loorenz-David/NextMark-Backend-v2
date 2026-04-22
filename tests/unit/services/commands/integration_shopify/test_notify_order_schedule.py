import importlib
from types import SimpleNamespace

module = importlib.import_module(
    "Delivery_app_BK.services.commands.integration_shopify.ingestions.outbound.order.notify_order_schedule"
)


def test_notify_order_schedule_posts_target_specific_payload(monkeypatch):
    target = SimpleNamespace(
        id=3,
        is_active=True,
        endpoint_url="https://example.com/hook",
        api_key="secret",
        external_shop_id="shop-44",
    )
    order = SimpleNamespace(
        id=19,
        external_order_id="98765",
    )
    post_calls: list[dict] = []

    def _fake_get(model, value):
        if value == 3:
            return target
        if value == 19:
            return order
        return None

    class _Response:
        def raise_for_status(self):
            return None

    monkeypatch.setattr(module.db.session, "get", _fake_get)
    monkeypatch.setattr(
        module.requests,
        "post",
        lambda url, **kwargs: post_calls.append({"url": url, **kwargs}) or _Response(),
    )

    module.notify_order_schedule(3, 19, "2026-04-25")

    assert post_calls == [
        {
            "url": "https://example.com/hook",
            "headers": {
                "x-api-key": "secret",
                "Content-Type": "application/json",
            },
            "json": {
                "shopId": "shop-44",
                "orderId": "98765",
                "scheduledDate": "2026-04-25",
            },
            "timeout": 10,
        }
    ]


def test_notify_order_schedule_returns_when_target_inactive(monkeypatch):
    target = SimpleNamespace(id=3, is_active=False)
    post_calls: list[dict] = []

    monkeypatch.setattr(module.db.session, "get", lambda model, value: target if value == 3 else None)
    monkeypatch.setattr(
        module.requests,
        "post",
        lambda *args, **kwargs: post_calls.append(kwargs),
    )

    module.notify_order_schedule(3, 19, "2026-04-25")

    assert post_calls == []


def test_notify_order_schedule_returns_for_non_external_orders(monkeypatch):
    target = SimpleNamespace(
        id=3,
        is_active=True,
        endpoint_url="https://example.com/hook",
        api_key="secret",
        external_shop_id="shop-44",
    )
    order = SimpleNamespace(id=19, external_order_id=None)
    post_calls: list[dict] = []

    def _fake_get(model, value):
        if value == 3:
            return target
        if value == 19:
            return order
        return None

    monkeypatch.setattr(module.db.session, "get", _fake_get)
    monkeypatch.setattr(
        module.requests,
        "post",
        lambda *args, **kwargs: post_calls.append(kwargs),
    )

    module.notify_order_schedule(3, 19, "2026-04-25")

    assert post_calls == []
