from __future__ import annotations

from Delivery_app_BK.models import OrderZoneAssignment, db
from Delivery_app_BK.services.commands.base.create_instance import create_instance

from ..context_builder import build_ctx
from ..registry import Registry


def process(item: dict, identity: dict, registry: Registry) -> int:
    fields = {key: value for key, value in item.items() if not key.startswith("_")}
    ctx = build_ctx(identity, {})
    instance = create_instance(ctx, OrderZoneAssignment, fields)
    db.session.add(instance)
    db.session.flush()
    return instance.id


__all__ = ["process"]
