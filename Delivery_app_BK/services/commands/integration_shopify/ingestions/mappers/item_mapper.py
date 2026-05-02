from Delivery_app_BK.services.commands.utils import generate_client_id
from .item_type_mapper import map_shopify_title_to_item_type


def _ensure_display_item_type(value):
    if not isinstance(value, str):
        return value
    cleaned = value.strip()
    if not cleaned:
        return cleaned
    return cleaned.replace("_", " ").strip().title()


def item_mapper(shopify_item):
    item_obj = {}

    if isinstance(shopify_item, dict):
        item_id = shopify_item.get("sku") or shopify_item.get("product_id")
        item_title = shopify_item.get("title") or shopify_item.get("name")
        item_type = _ensure_display_item_type(map_shopify_title_to_item_type(item_title))
        item_obj = {
            "client_id": generate_client_id('item'),
            "article_number": str(item_id),
            "quantity": shopify_item.get("quantity"),
            "item_type": item_type,
            "weight": shopify_item.get("grams"),
        }
    return item_obj