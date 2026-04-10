from __future__ import annotations

from Delivery_app_BK.models import Facility, db
from Delivery_app_BK.services.commands.base.create_instance import create_instance
from Delivery_app_BK.services.requests.infrastructure.facility import (
    parse_create_facility_request,
)

from ..context_builder import build_ctx
from ..registry import Registry


def process(item: dict, identity: dict, registry: Registry) -> int:
    fields = {key: value for key, value in item.items() if not key.startswith("_")}
    ctx = build_ctx(identity, {})
    request = parse_create_facility_request(fields)
    instance = create_instance(ctx, Facility, request.to_fields_dict())
    db.session.add(instance)
    db.session.flush()
    return instance.id


__all__ = ["process"]
