import importlib
from types import SimpleNamespace

from flask import Flask


module = importlib.import_module(
    "Delivery_app_BK.services.commands.integration_logistic.outbound.order.push_order_schedule_update"
)


def _build_app() -> Flask:
    return Flask(__name__)


def test_push_order_schedule_update_posts_expected_payload(monkeypatch):
    app = _build_app()
    app.config["EXTERNAL_API_URL"] = "https://example.com/events/order-schedule"
    app.config["EXTERNAL_API_KEY"] = "external-secret"
    app.config["EXTERNAL_API_TIMEOUT_SECONDS"] = 7

    post_calls: list[dict] = []

    class _Response:
        status_code = 200

        def json(self):
            return {"ok": True, "updated": 3}

    monkeypatch.setattr(
        module.requests,
        "post",
        lambda url, **kwargs: post_calls.append({"url": url, **kwargs}) or _Response(),
    )

    with app.app_context():
        result = module.push_order_schedule_update(
            shop_id="cl123",
            order_id="987654321",
            scheduled_date="2026-05-10",
        )

    assert result["status"] == "sent"
    assert result["updated"] == 3
    assert post_calls == [
        {
            "url": "https://example.com/events/order-schedule",
            "headers": {
                "x-api-key": "external-secret",
                "Content-Type": "application/json",
            },
            "json": {
                "shopId": "cl123",
                "orderId": "987654321",
                "scheduledDate": "2026-05-10",
            },
            "timeout": 7,
        }
    ]


def test_push_order_schedule_update_allows_empty_scheduled_date(monkeypatch):
    app = _build_app()
    app.config["EXTERNAL_API_URL"] = "https://example.com/events/order-schedule"
    app.config["EXTERNAL_API_KEY"] = "external-secret"

    calls: list[dict] = []

    class _Response:
        status_code = 200

        def json(self):
            return {"ok": True, "updated": 1}

    monkeypatch.setattr(
        module.requests,
        "post",
        lambda url, **kwargs: calls.append({"url": url, **kwargs}) or _Response(),
    )

    with app.app_context():
        result = module.push_order_schedule_update(
            shop_id="cl123",
            order_id="987654321",
            scheduled_date="",
        )

    assert result["status"] == "sent"
    assert calls[0]["json"]["scheduledDate"] == ""


def test_push_order_schedule_update_skips_when_date_invalid():
    app = _build_app()
    app.config["EXTERNAL_API_URL"] = "https://example.com/events/order-schedule"
    app.config["EXTERNAL_API_KEY"] = "external-secret"

    with app.app_context():
        result = module.push_order_schedule_update(
            shop_id="cl123",
            order_id="987654321",
            scheduled_date="2026/05/10",
        )

    assert result == {
        "status": "skipped",
        "reason": "scheduledDate must follow strict yyyy-mm-dd format or be empty",
    }


def test_push_order_schedule_update_raises_on_bad_http_status(monkeypatch):
    app = _build_app()
    app.config["EXTERNAL_API_URL"] = "https://example.com/events/order-schedule"
    app.config["EXTERNAL_API_KEY"] = "external-secret"

    monkeypatch.setattr(
        module.requests,
        "post",
        lambda *_args, **_kwargs: SimpleNamespace(status_code=401, text="unauthorized"),
    )

    with app.app_context():
        try:
            module.push_order_schedule_update(
                shop_id="cl123",
                order_id="987654321",
                scheduled_date="2026-05-10",
            )
            assert False, "expected RuntimeError"
        except RuntimeError as exc:
            assert "status 401" in str(exc)
