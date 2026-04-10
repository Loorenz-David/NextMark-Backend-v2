from __future__ import annotations

from typing import Any


COLLECTION_COLUMN_REGISTRY: dict[str, dict[str, Any]] = {
    "order": {
        "default": ["order_scalar_id", "client_name", "status", "street_address"],
        "allowed": {
            "order_scalar_id",
            "client_name",
            "status",
            "street_address",
            "total_items",
            "route_plan_id",
            "reference_number",
        },
    },
    "plan": {
        "default": ["plan_name", "plan_type", "orders_count", "status"],
        "allowed": {
            "plan_name",
            "plan_type",
            "orders_count",
            "status",
            "start_date",
            "end_date",
        },
    },
    "route": {
        "default": ["route_id", "plan_name", "driver_id", "stops_count"],
        "allowed": {
            "route_id",
            "plan_name",
            "driver_id",
            "stops_count",
            "status",
            "expected_start_time",
            "expected_end_time",
        },
    },
    "generic": {
        "default": [],
        "allowed": set(),
    },
}


_ORDER_SEARCH_FIELD_TO_COLUMN = {
    "order_scalar_id": "order_scalar_id",
    "reference_number": "reference_number",
    "client_first_name": "client_name",
    "client_last_name": "client_name",
    "client_email": "client_name",
    "client_address": "street_address",
    "client_address.street_address": "street_address",
    "route_plan_id": "route_plan_id",
}


def infer_collection_intent(
    entity_type: str,
    source_tool: str,
    params: dict,
    items: list[dict],
) -> dict:
    if entity_type == "order":
        return _infer_order_intent(source_tool, params)

    if entity_type == "plan":
        return _infer_plan_intent(source_tool, params)

    if entity_type == "route":
        return _infer_route_intent(source_tool, params)

    return {"mode": "default", "focus": []}


def resolve_collection_columns(
    entity_type: str,
    intent: dict | None,
    items: list[dict],
) -> list[str]:
    config = COLLECTION_COLUMN_REGISTRY.get(entity_type, COLLECTION_COLUMN_REGISTRY["generic"])
    allowed = config["allowed"]
    default_columns = list(config["default"])

    requested = list((intent or {}).get("focus") or [])
    prioritized = [column for column in requested if column in allowed]
    remaining = [column for column in default_columns if column not in prioritized]

    ordered = [column for column in prioritized + remaining if _column_has_value(column, items)]
    if ordered:
        return ordered

    fallback = [column for column in default_columns if _column_has_value(column, items)]
    if fallback:
        return fallback

    return default_columns


def build_collection_meta(
    entity_type: str,
    source_tool: str,
    params: dict,
    items: list[dict],
    *,
    layout: str,
    extra_meta: dict | None = None,
) -> dict:
    meta = dict(extra_meta or {})
    meta["source_tool"] = source_tool

    if layout == "table":
        intent = infer_collection_intent(entity_type, source_tool, params, items)
        meta["table"] = {"columns": resolve_collection_columns(entity_type, intent, items)}
        meta["presentation"] = {
            "density": "compact",
            "emphasis": "default",
        }

    return meta


def _infer_order_intent(source_tool: str, params: dict) -> dict:
    focus: list[str] = []
    search_fields = params.get("s") or []
    plan_id_column = "route_plan_id"

    for field in params.get("s") or []:
        column_id = _ORDER_SEARCH_FIELD_TO_COLUMN.get(field)
        if column_id and column_id not in focus:
            focus.append(column_id)

    if params.get("scheduled") is not None:
        if "status" not in focus:
            focus.append("status")
        if plan_id_column not in focus:
            focus.append(plan_id_column)

    if params.get("plan_id") is not None and plan_id_column not in focus:
        focus.append(plan_id_column)

    return {
        "mode": "search" if params.get("q") else "default",
        "focus": focus,
    }


def _infer_plan_intent(source_tool: str, params: dict) -> dict:
    focus: list[str] = []

    if params.get("label"):
        focus.append("plan_name")
    if params.get("plan_type"):
        focus.append("plan_type")
    if params.get("plan_state_id") is not None:
        focus.append("status")

    return {
        "mode": "search" if params.get("label") else "default",
        "focus": focus,
    }


def _infer_route_intent(source_tool: str, params: dict) -> dict:
    focus: list[str] = []

    if params.get("plan_id") is not None:
        focus.append("plan_name")
    if params.get("driver_id") is not None:
        focus.append("driver_id")
    if params.get("expected_start_after") or params.get("expected_start_before"):
        focus.append("expected_start_time")

    return {
        "mode": "search" if focus else "default",
        "focus": focus,
    }


def _column_has_value(column_id: str, items: list[dict]) -> bool:
    for item in items:
        value = item.get(column_id)
        if value not in (None, "", [], {}):
            return True
    return False