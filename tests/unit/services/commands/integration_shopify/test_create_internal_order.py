import importlib
from types import SimpleNamespace

import pytest

module = importlib.import_module(
    "Delivery_app_BK.services.commands.integration_shopify.ingestions.inbound.create_internal_order"
)


@pytest.fixture(autouse=True)
def _disable_shopify_image_lookup(monkeypatch):
    monkeypatch.setattr(
        module,
        "ShopifyLineItemMediaResolver",
        lambda *_args, **_kwargs: SimpleNamespace(
            get_line_item_images=lambda _line_item: [],
            get_line_item_page_link=lambda _line_item: None,
        ),
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


def test_create_internal_order_applies_shopify_item_images_after_filtering(monkeypatch):
    captured_create_order_ctx = {}
    captured_image_line_items = {}

    monkeypatch.setattr(
        module,
        "get_integration_by_shop",
        lambda _shop: SimpleNamespace(team_id=9, shop="demo.myshopify.com", access_token="token"),
    )
    monkeypatch.setattr(module, "order_mapper", lambda payload: {"client_id": "order_1"})
    monkeypatch.setattr(module, "item_mapper", lambda item: {"article_number": item.get("sku")})
    monkeypatch.setattr(
        module,
        "create_order",
        lambda ctx: captured_create_order_ctx.setdefault("incoming_data", ctx.incoming_data),
    )

    def _image_resolver(_integration, line_items):
        captured_image_line_items["skus"] = [line_item.get("sku") for line_item in line_items]
        return SimpleNamespace(
            get_line_item_images=lambda line_item: [
                f"https://cdn.example.com/{line_item['sku']}.jpg"
            ],
            get_line_item_page_link=lambda line_item: (
                f"https://demo-shop.com/products/{line_item['sku'].lower()}"
            ),
        )

    monkeypatch.setattr(module, "ShopifyLineItemMediaResolver", _image_resolver)

    module.create_internal_order(
        shop="demo.myshopify.com",
        payload={
            "line_items": [
                {"sku": "INTENT_STORE_PICKUP", "product_id": 1},
                {"sku": "SKU-1", "product_id": 2, "variant_id": 3},
            ],
        },
    )

    fields = captured_create_order_ctx["incoming_data"]["fields"]

    assert captured_image_line_items["skus"] == ["SKU-1"]
    assert fields["items"] == [
        {
            "article_number": "SKU-1",
            "item_images": ["https://cdn.example.com/SKU-1.jpg"],
            "page_link": "https://demo-shop.com/products/sku-1",
        }
    ]


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


def test_create_internal_order_enriches_chair_quantity_from_metafield_set_of(monkeypatch):
    captured_create_order_ctx = {}

    monkeypatch.setattr(
        module,
        "get_integration_by_shop",
        lambda _shop: SimpleNamespace(team_id=9, shop="demo.myshopify.com", access_token="token"),
    )
    monkeypatch.setattr(module, "order_mapper", lambda payload: {"client_id": "order_1"})
    monkeypatch.setattr(
        module,
        "item_mapper",
        lambda item: {
            "article_number": item.get("sku"),
            "item_type": item.get("title"),
            "quantity": item.get("quantity"),
        },
    )
    monkeypatch.setattr(
        module,
        "create_order",
        lambda ctx: captured_create_order_ctx.setdefault("incoming_data", ctx.incoming_data),
    )
    monkeypatch.setattr(
        module,
        "ShopifyMetafieldResolver",
        lambda _integration: SimpleNamespace(
            get_line_item_metafields=lambda _line_item: {"set_of": "4"}
        ),
    )

    module.create_internal_order(
        shop="demo.myshopify.com",
        payload={
            "line_items": [
                {
                    "sku": "SKU-CHAIR-1",
                    "title": "Dining Chair Set",
                    "quantity": 2,
                    "product_id": 123,
                }
            ],
        },
    )

    items = captured_create_order_ctx["incoming_data"]["fields"]["items"]
    assert items[0]["quantity"] == 8


def test_create_internal_order_keeps_non_chair_quantity_without_metafield_lookup(monkeypatch):
    captured_create_order_ctx = {}
    lookup_calls = {"count": 0}

    monkeypatch.setattr(
        module,
        "get_integration_by_shop",
        lambda _shop: SimpleNamespace(team_id=9, shop="demo.myshopify.com", access_token="token"),
    )
    monkeypatch.setattr(module, "order_mapper", lambda payload: {"client_id": "order_1"})
    monkeypatch.setattr(
        module,
        "item_mapper",
        lambda item: {
            "article_number": item.get("sku"),
            "item_type": item.get("title"),
            "quantity": item.get("quantity"),
        },
    )
    monkeypatch.setattr(
        module,
        "create_order",
        lambda ctx: captured_create_order_ctx.setdefault("incoming_data", ctx.incoming_data),
    )
    monkeypatch.setattr(
        module,
        "ShopifyMetafieldResolver",
        lambda _integration: SimpleNamespace(
            get_line_item_metafields=lambda _line_item: lookup_calls.__setitem__("count", lookup_calls["count"] + 1) or {}
        ),
    )

    module.create_internal_order(
        shop="demo.myshopify.com",
        payload={
            "line_items": [
                {
                    "sku": "SKU-TABLE-1",
                    "title": "Dining Table",
                    "quantity": 3,
                    "product_id": 321,
                }
            ],
        },
    )

    items = captured_create_order_ctx["incoming_data"]["fields"]["items"]
    assert items[0]["quantity"] == 3
    assert lookup_calls["count"] == 0
