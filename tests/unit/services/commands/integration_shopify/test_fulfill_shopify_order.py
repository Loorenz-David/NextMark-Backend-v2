import importlib
from types import SimpleNamespace

module = importlib.import_module(
    "Delivery_app_BK.services.commands.integration_shopify.ingestions.outbound.order.fulfill_shopify_order"
)


def test_fulfill_shopify_order_creates_fulfillment_for_supported_orders(monkeypatch):
    order = SimpleNamespace(
        id=14,
        team_id=7,
        external_source="shopify",
        external_order_id="98765",
    )
    integration = SimpleNamespace(team_id=7, shop="demo.myshopify.com", access_token="secret")
    graphql_calls: list[dict] = []

    monkeypatch.setattr(module.db.session, "get", lambda model, value: order if value == 14 else None)
    monkeypatch.setattr(
        module.db.session,
        "query",
        lambda _model: SimpleNamespace(
            filter=lambda *args, **kwargs: SimpleNamespace(
                order_by=lambda *a, **k: SimpleNamespace(first=lambda: integration)
            )
        ),
    )

    def _fake_post_shopify_graphql(*, integration, query, variables):
        graphql_calls.append({"query": query, "variables": variables})
        if "query getOrderFulfillmentOrders" in query:
            return {
                "order": {
                    "fulfillmentOrders": {
                        "nodes": [
                            {
                                "id": "gid://shopify/FulfillmentOrder/1",
                                "supportedActions": [{"action": "CREATE_FULFILLMENT"}],
                            },
                            {
                                "id": "gid://shopify/FulfillmentOrder/2",
                                "supportedActions": [{"action": "HOLD"}],
                            },
                        ]
                    }
                }
            }
        return {"fulfillmentCreate": {"fulfillment": {"id": "gid://shopify/Fulfillment/11"}, "userErrors": []}}

    monkeypatch.setattr(module, "_post_shopify_graphql", _fake_post_shopify_graphql)

    module.fulfill_shopify_order(14)

    assert len(graphql_calls) == 2
    assert graphql_calls[0]["variables"] == {"orderId": "gid://shopify/Order/98765"}
    assert graphql_calls[1]["variables"] == {
        "fulfillment": {
            "notifyCustomer": False,
            "lineItemsByFulfillmentOrder": [
                {"fulfillmentOrderId": "gid://shopify/FulfillmentOrder/1"},
            ],
        }
    }


def test_fulfill_shopify_order_returns_when_no_supported_fulfillment_orders(monkeypatch):
    order = SimpleNamespace(
        id=14,
        team_id=7,
        external_source="shopify",
        external_order_id="98765",
    )
    integration = SimpleNamespace(team_id=7, shop="demo.myshopify.com", access_token="secret")
    graphql_calls: list[dict] = []

    monkeypatch.setattr(module.db.session, "get", lambda model, value: order if value == 14 else None)
    monkeypatch.setattr(
        module.db.session,
        "query",
        lambda _model: SimpleNamespace(
            filter=lambda *args, **kwargs: SimpleNamespace(
                order_by=lambda *a, **k: SimpleNamespace(first=lambda: integration)
            )
        ),
    )
    monkeypatch.setattr(
        module,
        "_post_shopify_graphql",
        lambda **kwargs: graphql_calls.append(kwargs) or {
            "order": {"fulfillmentOrders": {"nodes": [{"id": "gid://shopify/FulfillmentOrder/1", "supportedActions": []}]}}
        },
    )

    module.fulfill_shopify_order(14)

    assert len(graphql_calls) == 1
