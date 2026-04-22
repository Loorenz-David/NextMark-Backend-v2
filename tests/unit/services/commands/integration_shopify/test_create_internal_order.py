import importlib
from types import SimpleNamespace

module = importlib.import_module(
    "Delivery_app_BK.services.commands.integration_shopify.ingestions.inbound.create_internal_order"
)


def test_create_internal_order_creates_costumer_before_order_when_customer_present(monkeypatch):
    captured_create_order_ctx = {}

    monkeypatch.setattr(module, "get_integration_by_shop", lambda _shop: SimpleNamespace(team_id=9))
    monkeypatch.setattr(module, "order_mapper", lambda payload: {"client_id": "order_1", "client_email": "client@example.com"})
    monkeypatch.setattr(module, "item_mapper", lambda item: {"article_number": item.get("sku")})
    monkeypatch.setattr(
        module,
        "_resolve_or_create_shopify_costumer_id",
        lambda **kwargs: 77,
    )
    monkeypatch.setattr(
        module,
        "create_order",
        lambda ctx: captured_create_order_ctx.setdefault("incoming_data", ctx.incoming_data),
    )

    module.create_internal_order(
        shop="demo.myshopify.com",
        payload={
            "id": 1000,
            "customer": {
                "id": 555,
                "first_name": "Martha",
                "last_name": "Jones",
                "email": "martha@example.com",
            },
            "line_items": [{"sku": "SKU-1"}],
        },
    )

    assert captured_create_order_ctx["incoming_data"]["fields"]["items"] == [{"article_number": "SKU-1"}]
    assert captured_create_order_ctx["incoming_data"]["fields"]["order_plan_objective"] == "local_delivery"
    assert captured_create_order_ctx["incoming_data"]["fields"]["costumer"] == {"costumer_id": 77}


def test_create_internal_order_reuses_existing_shopify_costumer(monkeypatch):
    monkeypatch.setattr(module, "get_integration_by_shop", lambda _shop: SimpleNamespace(team_id=9))
    monkeypatch.setattr(module, "order_mapper", lambda payload: {"client_id": "order_1"})
    monkeypatch.setattr(module, "item_mapper", lambda item: item)
    monkeypatch.setattr(
        module.db.session,
        "query",
        lambda _model: SimpleNamespace(
            filter=lambda *args, **kwargs: SimpleNamespace(first=lambda: SimpleNamespace(id=88))
        ),
    )

    reused_id = module._resolve_or_create_shopify_costumer_id(
        team_id=9,
        shopify_customer={"id": 111},
        order_payload={"client_first_name": "A", "client_last_name": "B"},
    )

    assert reused_id == 88


def test_create_internal_order_sets_plan_objective_and_filters_reserved_skus(monkeypatch):
    captured_create_order_ctx = {}

    monkeypatch.setattr(module, "get_integration_by_shop", lambda _shop: SimpleNamespace(team_id=9))
    monkeypatch.setattr(module, "order_mapper", lambda payload: {"client_id": "order_1"})
    monkeypatch.setattr(module, "item_mapper", lambda item: {"article_number": item.get("sku")})
    monkeypatch.setattr(
        module,
        "create_order",
        lambda ctx: captured_create_order_ctx.setdefault("incoming_data", ctx.incoming_data),
    )

    module.create_internal_order(
        shop="demo.myshopify.com",
        payload={
            "line_items": [
                {"sku": "INTENT_STORE_PICKUP"},
                {"sku": "FLAG_NEEDS_FIXING"},
                {"sku": "SKU-1"},
            ],
        },
    )

    fields = captured_create_order_ctx["incoming_data"]["fields"]

    assert fields["order_plan_objective"] == "store_pickup"
    assert fields["items"] == [{"article_number": "SKU-1"}]


def test_create_internal_order_suppresses_customer_took_it_orders(monkeypatch):
    monkeypatch.setattr(module, "get_integration_by_shop", lambda _shop: SimpleNamespace(team_id=9))
    monkeypatch.setattr(module, "order_mapper", lambda payload: {"client_id": "order_1"})
    monkeypatch.setattr(module, "item_mapper", lambda item: {"article_number": item.get("sku")})

    create_order_called = False

    def _create_order(_ctx):
        nonlocal create_order_called
        create_order_called = True

    monkeypatch.setattr(module, "create_order", _create_order)

    module.create_internal_order(
        shop="demo.myshopify.com",
        payload={
            "line_items": [
                {"sku": "INTENT_CUSTOMER_TOOK_IT"},
                {"sku": "SKU-1"},
            ],
        },
    )

    assert create_order_called is False
