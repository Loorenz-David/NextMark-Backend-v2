from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.requests.common.fields import validate_unexpected


SELECTION_ALLOWED_FIELDS = {
    "manual_order_ids",
    "select_all_snapshots",
    "excluded_order_ids",
    "source",
}

SNAPSHOT_ALLOWED_FIELDS = {
    "query",
    "client_signature",
}

MAX_MANUAL_IDS = 5000
MAX_SNAPSHOTS_PER_PAYLOAD = 10
MAX_EXCLUSIONS = 5000

FORBIDDEN_PAGINATION_KEYS = {
    "after_date",
    "after_id",
    "before_date",
    "before_id",
    "limit",
    "cursor",
    "page",
    "sort",
}

ALLOWED_SNAPSHOT_FILTERS = {
    "route_plan_id",
    "q",
    "s",
    "show_archived",
    "schedule_order",
    "unschedule_order",
    "earliest_delivery_date",
    "operation_type",
    "latest_delivery_date",
    "creation_date_from",
    "creation_date_to",
    "order_state_id",
    "reference_number",
    "external_source",
    "tracking_number",
    "client_name",
    "client_email",
    "client_address",
    "client_phone",
    "plan_label",
    "plan_type",
    "article_number",
    "item_type",
    "items",
}

ALLOWED_ITEMS_FILTERS = {
    "q",
    "client_id",
    "article_number",
    "item_type",
    "item_state_id",
    "item_position_id",
    "order_id",
    "weight_min",
    "weight_max",
}

BOOLEAN_FILTER_KEYS = {
    "show_archived",
    "schedule_order",
    "unschedule_order",
}

INT_OR_INT_LIST_FILTER_KEYS = {
    "order_state_id",
}

ITEM_INT_OR_INT_LIST_FILTER_KEYS = {
    "item_state_id",
    "item_position_id",
    "order_id",
}

ITEM_NUMERIC_FILTER_KEYS = {
    "weight_min",
    "weight_max",
}


@dataclass(frozen=True)
class OrderSelectAllSnapshotRequest:
    query: dict[str, Any]
    client_signature: str | None
    signature: str


@dataclass(frozen=True)
class OrderBatchSelectionRequest:
    manual_order_ids: list[int]
    select_all_snapshots: list[OrderSelectAllSnapshotRequest]
    excluded_order_ids: list[int]
    source: str | None
    signature: str


def parse_update_orders_route_plan_batch_request(raw: Any) -> OrderBatchSelectionRequest:
    if not isinstance(raw, dict):
        raise ValidationFailed("selection payload must be an object.")

    validate_unexpected(
        raw,
        SELECTION_ALLOWED_FIELDS,
        context_msg="Unexpected fields in selection payload:",
    )

    manual_order_ids = _parse_id_list(
        raw.get("manual_order_ids"),
        field="manual_order_ids",
        max_count=MAX_MANUAL_IDS,
        over_limit_message="Too many manually selected orders. Please refine your selection.",
    )
    excluded_order_ids = _parse_id_list(
        raw.get("excluded_order_ids"),
        field="excluded_order_ids",
        max_count=MAX_EXCLUSIONS,
    )
    select_all_snapshots = _parse_snapshots(raw.get("select_all_snapshots"))
    source = _parse_source(raw.get("source"))

    selection_signature = _build_selection_signature(
        manual_order_ids=manual_order_ids,
        select_all_snapshots=select_all_snapshots,
        excluded_order_ids=excluded_order_ids,
    )

    return OrderBatchSelectionRequest(
        manual_order_ids=manual_order_ids,
        select_all_snapshots=select_all_snapshots,
        excluded_order_ids=excluded_order_ids,
        source=source,
        signature=selection_signature,
    )


def _parse_source(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationFailed("selection.source must be a string when provided.")
    normalized = value.strip().lower()
    if not normalized:
        return None
    allowed = {"single", "group", "selection"}
    if normalized not in allowed:
        raise ValidationFailed("selection.source must be one of: single, group, selection.")
    return normalized


def parse_update_orders_route_plan_batch_payload(raw: Any) -> OrderBatchSelectionRequest:
    if not isinstance(raw, dict):
        raise ValidationFailed("Request payload must be an object.")
    if "selection" not in raw:
        raise ValidationFailed("Missing key 'selection' in request payload.")
    return parse_update_orders_route_plan_batch_request(raw.get("selection"))


def _parse_snapshots(value: Any) -> list[OrderSelectAllSnapshotRequest]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationFailed("select_all_snapshots must be a list of objects.")
    if len(value) > MAX_SNAPSHOTS_PER_PAYLOAD:
        raise ValidationFailed(
            f"select_all_snapshots supports at most {MAX_SNAPSHOTS_PER_PAYLOAD} snapshots.",
        )

    snapshots: list[OrderSelectAllSnapshotRequest] = []
    seen_signatures: set[str] = set()
    for index, row in enumerate(value):
        if not isinstance(row, dict):
            raise ValidationFailed(f"select_all_snapshots[{index}] must be an object.")
        validate_unexpected(
            row,
            SNAPSHOT_ALLOWED_FIELDS,
            context_msg=f"Unexpected fields in select_all_snapshots[{index}]:",
        )

        query = _sanitize_snapshot_query(row.get("query"), field=f"select_all_snapshots[{index}].query")
        signature = _stable_json(query)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)

        client_signature = row.get("client_signature")
        if client_signature is not None and not isinstance(client_signature, str):
            raise ValidationFailed(
                f"select_all_snapshots[{index}].client_signature must be a string when provided.",
            )

        snapshots.append(
            OrderSelectAllSnapshotRequest(
                query=query,
                client_signature=client_signature.strip() if isinstance(client_signature, str) else None,
                signature=signature,
            )
        )

    return snapshots


def _sanitize_snapshot_query(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationFailed(f"{field} must be an object.")

    incoming_keys = set(value.keys())
    forbidden_keys = sorted(incoming_keys.intersection(FORBIDDEN_PAGINATION_KEYS))
    if forbidden_keys:
        raise ValidationFailed(f"{field} contains forbidden pagination keys: {forbidden_keys}.")

    unknown_keys = sorted(incoming_keys - ALLOWED_SNAPSHOT_FILTERS)
    if unknown_keys:
        raise ValidationFailed(f"{field} contains unsupported filters: {unknown_keys}.")

    normalized: dict[str, Any] = {}

    route_plan_id_raw = value.get("route_plan_id")
    if route_plan_id_raw not in (None, ""):
        route_plan_id = _normalize_int_or_int_list(
            route_plan_id_raw,
            field=f"{field}.route_plan_id",
        )
        if route_plan_id is not None:
            normalized["route_plan_id"] = route_plan_id

    for key in sorted(ALLOWED_SNAPSHOT_FILTERS):
        if key not in value:
            continue
        if key in {"route_plan_id"}:
            continue
        raw = value.get(key)
        if raw is None or raw == "":
            continue

        if key == "q":
            if not isinstance(raw, str):
                raise ValidationFailed(f"{field}.q must be a string.")
            trimmed = raw.strip()
            if trimmed:
                normalized["q"] = trimmed
            continue

        if key == "s":
            normalized_s = _normalize_string_filters(raw, field=f"{field}.s")
            if normalized_s:
                normalized["s"] = normalized_s
            continue

        if key == "items":
            normalized_items = _sanitize_items_query(raw, field=f"{field}.items")
            if normalized_items:
                normalized["items"] = normalized_items
            continue

        if key in BOOLEAN_FILTER_KEYS:
            if type(raw) is not bool:
                raise ValidationFailed(f"{field}.{key} must be a boolean.")
            normalized[key] = raw
            continue

        if key in INT_OR_INT_LIST_FILTER_KEYS:
            normalized_value = _normalize_int_or_int_list(raw, field=f"{field}.{key}")
            if normalized_value is not None:
                normalized[key] = normalized_value
            continue

        if not isinstance(raw, (str, int, float)):
            raise ValidationFailed(f"{field}.{key} must be a string or number.")
        normalized[key] = raw.strip() if isinstance(raw, str) else raw

    return normalized


def _sanitize_items_query(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationFailed(f"{field} must be an object.")

    unknown_keys = sorted(set(value.keys()) - ALLOWED_ITEMS_FILTERS)
    if unknown_keys:
        raise ValidationFailed(f"{field} contains unsupported filters: {unknown_keys}.")

    normalized: dict[str, Any] = {}
    for key in sorted(ALLOWED_ITEMS_FILTERS):
        if key not in value:
            continue
        raw = value.get(key)
        if raw is None or raw == "":
            continue

        if key in {"q", "client_id", "article_number", "item_type"}:
            if not isinstance(raw, str):
                raise ValidationFailed(f"{field}.{key} must be a string.")
            trimmed = raw.strip()
            if trimmed:
                normalized[key] = trimmed
            continue

        if key in ITEM_INT_OR_INT_LIST_FILTER_KEYS:
            normalized_value = _normalize_int_or_int_list(raw, field=f"{field}.{key}")
            if normalized_value is not None:
                normalized[key] = normalized_value
            continue

        if key in ITEM_NUMERIC_FILTER_KEYS:
            if type(raw) in {int, float} and not isinstance(raw, bool):
                normalized[key] = raw
                continue
            raise ValidationFailed(f"{field}.{key} must be a number.")

    return normalized


def _normalize_string_filters(value: Any, *, field: str) -> list[str]:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                value = parsed
            else:
                value = [token.strip() for token in stripped.split(",") if token.strip()]
        except json.JSONDecodeError:
            value = [token.strip() for token in stripped.split(",") if token.strip()]

    if not isinstance(value, list):
        raise ValidationFailed(f"{field} must be a list of strings.")

    normalized: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ValidationFailed(f"{field}[{index}] must be a string.")
        trimmed = item.strip()
        if trimmed:
            normalized.append(trimmed)

    return sorted(set(normalized))


def _normalize_int_or_int_list(value: Any, *, field: str) -> int | list[int] | None:
    if value is None:
        return None
    if type(value) is int:
        if value <= 0:
            raise ValidationFailed(f"{field} must be greater than 0.")
        return value
    if isinstance(value, list):
        parsed = _parse_id_list(
            value,
            field=field,
            max_count=5000,
        )
        return parsed

    raise ValidationFailed(f"{field} must be an integer or list of integers.")


def _parse_id_list(
    value: Any,
    *,
    field: str,
    max_count: int,
    over_limit_message: str | None = None,
) -> list[int]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationFailed(f"{field} must be a list of integers.")
    if len(value) > max_count:
        raise ValidationFailed(over_limit_message or f"{field} exceeds max size of {max_count}.")

    parsed: list[int] = []
    seen: set[int] = set()
    for index, item in enumerate(value):
        if type(item) is not int:
            raise ValidationFailed(f"{field}[{index}] must be an integer.")
        if item <= 0:
            raise ValidationFailed(f"{field}[{index}] must be greater than 0.")
        if item in seen:
            continue
        seen.add(item)
        parsed.append(item)
    return parsed


def _build_selection_signature(
    *,
    manual_order_ids: list[int],
    select_all_snapshots: list[OrderSelectAllSnapshotRequest],
    excluded_order_ids: list[int],
) -> str:
    payload = {
        "manual_order_ids": manual_order_ids,
        "select_all_snapshots": [
            {"query": snapshot.query, "signature": snapshot.signature}
            for snapshot in select_all_snapshots
        ],
        "excluded_order_ids": excluded_order_ids,
    }
    return _stable_json(payload)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
