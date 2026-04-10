from __future__ import annotations

from Delivery_app_BK.services.commands.order.create_order import create_order

from ..client_ids import apply_test_data_client_id_to_order_children
from ..context_builder import build_ctx
from ..registry import Registry


def process(item: dict, identity: dict, registry: Registry) -> int:
    fields = {key: value for key, value in item.items() if not key.startswith("_")}
    fields = apply_test_data_client_id_to_order_children(fields)
    ctx = build_ctx(identity, {"fields": [fields]})
    result = create_order(ctx)
    return result["created"][0]["order"]["id"]


__all__ = ["process"]
