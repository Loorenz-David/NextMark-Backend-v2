from __future__ import annotations

from types import SimpleNamespace

from Delivery_app_BK.services.commands.order.create_serializers import (
    serialize_created_items,
)


def test_serialize_created_items_includes_item_images():
    item = SimpleNamespace(
        id=1,
        client_id="item_1",
        article_number="SKU-1",
        reference_number=None,
        item_type="Dining chair",
        item_state_id=1,
        item_position=None,
        order_id=10,
        properties=[],
        page_link=None,
        item_images=["https://cdn.example.com/items/sku-1.jpg"],
        dimension_depth=None,
        dimension_height=None,
        dimension_width=None,
        weight=None,
        quantity=1,
    )

    serialized = serialize_created_items([item])

    assert serialized[0]["item_images"] == ["https://cdn.example.com/items/sku-1.jpg"]


def test_serialize_created_items_defaults_missing_item_images_to_empty_list():
    item = SimpleNamespace(
        id=1,
        client_id="item_1",
        article_number="SKU-1",
        reference_number=None,
        item_type="Dining chair",
        item_state_id=1,
        item_position=None,
        order_id=10,
        properties=[],
        page_link=None,
        item_images=None,
        dimension_depth=None,
        dimension_height=None,
        dimension_width=None,
        weight=None,
        quantity=1,
    )

    serialized = serialize_created_items([item])

    assert serialized[0]["item_images"] == []
