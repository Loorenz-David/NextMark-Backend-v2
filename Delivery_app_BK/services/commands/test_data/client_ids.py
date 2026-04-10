from __future__ import annotations

import re
from contextlib import contextmanager
from uuid import uuid4

from Delivery_app_BK.services.commands.utils.client_id_generator import (
    apply_client_id_namespace,
    reset_client_id_namespace,
    set_client_id_namespace,
)


DEFAULT_TEST_DATA_CLIENT_ID_PREFIX = "td:"

CLIENT_ID_ENTITY_KEYS = frozenset(
    {
        "item_property",
        "item_type",
        "facility",
        "vehicle",
        "route_plan",
        "order",
        "order_delivery_window",
    }
)


@contextmanager
def test_data_client_id_namespace(prefix: str | None = None):
    token = set_client_id_namespace(prefix or DEFAULT_TEST_DATA_CLIENT_ID_PREFIX)
    try:
        yield
    finally:
        reset_client_id_namespace(token)


def apply_test_data_client_id(entity_key: str, item: dict, *, sid: str | None = None) -> dict:
    if entity_key not in CLIENT_ID_ENTITY_KEYS:
        return dict(item)

    output = dict(item)
    output["client_id"] = build_test_data_client_id(
        entity_key,
        sid=sid,
        existing_client_id=item.get("client_id"),
    )
    return output


def apply_test_data_client_id_to_order_children(order_fields: dict) -> dict:
    output = dict(order_fields)

    if isinstance(output.get("items"), list):
        output["items"] = [
            _with_client_id("item", item, fallback=f"item_{index}")
            for index, item in enumerate(output["items"])
        ]

    if isinstance(output.get("delivery_windows"), list):
        output["delivery_windows"] = [
            _with_client_id("order_delivery_window", window, fallback=f"window_{index}")
            for index, window in enumerate(output["delivery_windows"])
        ]

    return output


def resolve_test_data_client_id_prefix(payload: dict) -> str:
    meta = payload.get("_meta")
    if isinstance(meta, dict):
        configured = meta.get("client_id_prefix")
        if isinstance(configured, str) and configured.strip():
            return configured.strip()
    return DEFAULT_TEST_DATA_CLIENT_ID_PREFIX


def build_test_data_client_id(
    entity_key: str,
    *,
    sid: str | None = None,
    existing_client_id: str | None = None,
    fallback: str | None = None,
) -> str:
    base = None
    if isinstance(existing_client_id, str) and existing_client_id.strip():
        base = existing_client_id.strip()
    elif isinstance(sid, str) and sid.strip():
        base = sid.strip()
    elif isinstance(fallback, str) and fallback.strip():
        base = fallback.strip()
    else:
        base = entity_key

    safe_base = re.sub(r"[^A-Za-z0-9:_-]+", "_", base)
    namespaced = f"{entity_key}:{safe_base}:{uuid4().hex}"
    return apply_client_id_namespace(namespaced)


def _with_client_id(entity_key: str, raw_item: object, *, fallback: str) -> object:
    if not isinstance(raw_item, dict):
        return raw_item

    output = dict(raw_item)
    output["client_id"] = build_test_data_client_id(
        entity_key,
        existing_client_id=output.get("client_id"),
        fallback=fallback,
    )
    return output
