from __future__ import annotations

from Delivery_app_BK.models import Vehicle, db
from Delivery_app_BK.services.commands.base.create_instance import create_instance
from Delivery_app_BK.services.requests.infrastructure.vehicle.parse_vehicle_request import (
    parse_create_vehicle_request,
)

from ..context_builder import build_ctx
from ..registry import Registry


def process(item: dict, identity: dict, registry: Registry) -> int:
    fields = {key: value for key, value in item.items() if not key.startswith("_")}
    ctx = build_ctx(identity, {})
    request = parse_create_vehicle_request(fields)
    instance = create_instance(ctx, Vehicle, request.to_fields_dict())
    db.session.add(instance)
    db.session.flush()
    return instance.id


__all__ = ["process"]
