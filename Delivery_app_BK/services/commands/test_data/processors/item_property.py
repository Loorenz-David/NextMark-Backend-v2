from __future__ import annotations

from Delivery_app_BK.services.commands.item.create.create_item_property import (
    create_item_property,
)

from ..context_builder import build_ctx
from ..registry import Registry


def process(item: dict, identity: dict, registry: Registry) -> int:
    fields = {key: value for key, value in item.items() if not key.startswith("_")}
    fields.setdefault("required", False)
    ctx = build_ctx(identity, {"fields": [fields]}, on_create_return="instances")
    result = create_item_property(ctx)
    return result[0].id


__all__ = ["process"]
