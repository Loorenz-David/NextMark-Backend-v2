from __future__ import annotations

from typing import Any

from .client_ids import (
    apply_test_data_client_id,
    resolve_test_data_client_id_prefix,
    test_data_client_id_namespace,
)
from .registry import Registry
from .resolver import resolve_item
from .processors import (
    item_property as item_property_processor,
    item_type as item_type_processor,
    facility as facility_processor,
    vehicle as vehicle_processor,
    zone_version as zone_version_processor,
    zone as zone_processor,
    zone_template as zone_template_processor,
    route_plan as route_plan_processor,
    order as order_processor,
    order_delivery_window as order_delivery_window_processor,
    order_zone_assignment as order_zone_assignment_processor,
)


PROCESSING_ORDER: list[str] = [
    "item_property",
    "item_type",
    "facility",
    "vehicle",
    "zone_version",
    "zone",
    "zone_template",
    "route_plan",
    "order",
    "order_delivery_window",
    "order_zone_assignment",
]

PROCESSOR_MAP = {
    "item_property": item_property_processor.process,
    "item_type": item_type_processor.process,
    "facility": facility_processor.process,
    "vehicle": vehicle_processor.process,
    "zone_version": zone_version_processor.process,
    "zone": zone_processor.process,
    "zone_template": zone_template_processor.process,
    "route_plan": route_plan_processor.process,
    "order": order_processor.process,
    "order_delivery_window": order_delivery_window_processor.process,
    "order_zone_assignment": order_zone_assignment_processor.process,
}


def create_test_data(identity: dict, payload: dict) -> dict[str, Any]:
    """Process a JSON payload and create entities in fixed topological order."""
    allowed_meta_keys = {"_meta"}
    unknown_keys = set(payload.keys()) - set(PROCESSING_ORDER) - allowed_meta_keys
    if unknown_keys:
        raise ValueError(
            f"Unknown entity keys in payload: {sorted(unknown_keys)}. "
            f"Supported keys: {PROCESSING_ORDER}"
        )

    registry = Registry()
    results: dict[str, Any] = {}
    client_id_prefix = resolve_test_data_client_id_prefix(payload)

    with test_data_client_id_namespace(client_id_prefix):
        for entity_key in PROCESSING_ORDER:
            if entity_key not in payload:
                continue
            items = payload.get(entity_key)

            if not isinstance(items, list):
                raise ValueError(f"Payload key {entity_key!r} must be a list.")

            if not items:
                continue

            created_ids: list[int] = []

            for index, raw_item in enumerate(items):
                if not isinstance(raw_item, dict):
                    raise ValueError(
                        f"Each item in {entity_key!r} must be a dict. "
                        f"Got {type(raw_item).__name__!r} at index {index}."
                    )

                sid: str | None = raw_item.get("$id")

                zone_sids: list[str] = []
                if entity_key == "route_plan":
                    raw_zones = raw_item.get("$zones")
                    if isinstance(raw_zones, list):
                        zone_sids = [zone_sid for zone_sid in raw_zones if isinstance(zone_sid, str)]

                resolved = resolve_item(entity_key, raw_item, registry)
                resolved = apply_test_data_client_id(entity_key, resolved, sid=sid)

                if sid:
                    resolved["_sid"] = sid
                if zone_sids:
                    resolved["_zone_sids"] = zone_sids

                db_id: int = PROCESSOR_MAP[entity_key](resolved, identity, registry)

                if sid:
                    registry.register(sid, db_id, entity_key)

                created_ids.append(db_id)

            results[entity_key] = {"count": len(created_ids), "ids": created_ids}

    return results


__all__ = ["create_test_data", "PROCESSING_ORDER"]
