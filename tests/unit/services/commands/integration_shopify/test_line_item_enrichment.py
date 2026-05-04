from __future__ import annotations

import importlib
from types import SimpleNamespace

module = importlib.import_module(
    "Delivery_app_BK.services.commands.integration_shopify.ingestions.inbound.line_item_enrichment"
)


def test_shopify_line_item_image_resolver_fetches_images_in_one_nodes_query(monkeypatch):
    captured = {}

    def _post_shopify_graphql(*, integration, query, variables):
        captured["integration"] = integration
        captured["query"] = query
        captured["variables"] = variables
        return {
            "nodes": [
                {
                    "id": "gid://shopify/ProductVariant/30",
                    "image": {"url": "https://cdn.example.com/variant-30.jpg"},
                    "product": {
                        "onlineStoreUrl": "https://shop.example.com/products/chair",
                        "handle": "chair",
                    },
                },
                {
                    "id": "gid://shopify/Product/20",
                    "onlineStoreUrl": None,
                    "handle": "table",
                    "featuredMedia": {
                        "preview": {
                            "image": {"url": "https://cdn.example.com/product-20-featured.jpg"}
                        }
                    },
                    "images": {
                        "nodes": [
                            {"url": "https://cdn.example.com/product-20-featured.jpg"},
                            {"url": "https://cdn.example.com/product-20-side.jpg"},
                        ]
                    },
                },
            ]
        }

    monkeypatch.setattr(module, "_post_shopify_graphql", _post_shopify_graphql)

    integration = SimpleNamespace(shop="demo.myshopify.com", access_token="token")
    resolver = module.ShopifyLineItemMediaResolver(
        integration,
        [
            {"product_id": 20, "variant_id": 30},
            {"product_id": 20, "variant_id": 30},
        ],
    )

    images = resolver.get_line_item_images({"product_id": 20, "variant_id": 30})
    page_link = resolver.get_line_item_page_link({"product_id": 20, "variant_id": 30})
    fallback_images = resolver.get_line_item_images({"product_id": 20})
    fallback_page_link = resolver.get_line_item_page_link({"product_id": 20})

    assert images == ["https://cdn.example.com/variant-30.jpg"]
    assert page_link == "https://shop.example.com/products/chair?variant=30"
    assert fallback_images == [
        "https://cdn.example.com/product-20-featured.jpg",
        "https://cdn.example.com/product-20-side.jpg",
    ]
    assert fallback_page_link == "https://demo.myshopify.com/products/table"
    assert captured["integration"] is integration
    assert captured["variables"]["ids"] == [
        "gid://shopify/ProductVariant/30",
        "gid://shopify/Product/20",
    ]
    assert "nodes(ids: $ids)" in captured["query"]


def test_apply_shopify_line_item_media_leaves_item_unchanged_when_no_media():
    item = {"article_number": "SKU-1"}
    resolver = SimpleNamespace(
        get_line_item_images=lambda _line_item: [],
        get_line_item_page_link=lambda _line_item: None,
    )

    enriched = module.apply_shopify_line_item_media(
        mapped_item=item,
        line_item={"product_id": 20},
        resolver=resolver,
    )

    assert enriched is item
