from Delivery_app_BK.services.commands.utils import generate_client_id

def item_mapper(shopify_item):
    item_obj = {}

    if isinstance(shopify_item, dict):
        item_id = shopify_item.get("sku") or shopify_item.get("product_id")
        item_type = shopify_item.get("name") or shopify_item.get("title")
        item_obj = {
            "client_id": generate_client_id('item'),
            "article_number": str(item_id),
            "quantity": shopify_item.get("quantity"),
            "item_type": item_type,
            "weight": shopify_item.get("grams"),
        }
    return item_obj