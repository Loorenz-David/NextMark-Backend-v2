from __future__ import annotations


REF_FIELD_MAP: dict[str, dict[str, str | tuple[str, str]]] = {
    "item_type": {
        "$properties": ("properties", "list"),
    },
    "vehicle": {
        "$facility": "home_facility_id",
    },
    "zone": {
        "$zone_version": "version_id",
    },
    "zone_template": {
        "$zone": "zone_id",
        "$facility": "default_facility_id",
    },
    "route_plan": {
        "$zones": ("zone_ids", "list"),
    },
    "order": {
        "$route_plan": "delivery_plan_id",
        "$route_group": "route_group_id",
    },
    "order_delivery_window": {
        "$order": "order_id",
    },
    "order_zone_assignment": {
        "$order": "order_id",
        "$zone": "zone_id",
        "$zone_version": "zone_version_id",
    },
}


__all__ = ["REF_FIELD_MAP"]
