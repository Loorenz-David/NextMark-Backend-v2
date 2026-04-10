from __future__ import annotations

from Delivery_app_BK.services.commands.zones.create_zone_template import create_zone_template

from ..context_builder import build_ctx
from ..registry import Registry


def process(item: dict, identity: dict, registry: Registry) -> int:
    fields = {key: value for key, value in item.items() if not key.startswith("_")}
    ctx = build_ctx(identity, fields)
    result = create_zone_template(ctx)
    return result["id"]


__all__ = ["process"]
