from __future__ import annotations

import pytest

from Delivery_app_BK.models import Item


def test_item_images_accepts_list_of_strings():
    item = Item()

    item.item_images = ["https://cdn.example.com/items/sku-1.jpg"]

    assert item.item_images == ["https://cdn.example.com/items/sku-1.jpg"]


def test_item_images_rejects_non_string_entries():
    item = Item()

    with pytest.raises(ValueError):
        item.item_images = ["https://cdn.example.com/items/sku-1.jpg", 3]
