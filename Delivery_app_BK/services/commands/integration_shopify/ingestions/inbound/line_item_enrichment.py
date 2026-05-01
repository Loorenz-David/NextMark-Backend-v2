from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Callable

import requests

from Delivery_app_BK.models import ShopifyIntegration


logger = logging.getLogger(__name__)

SHOPIFY_ADMIN_API_VERSION = "2026-04"
CHAIR_QUANTITY_METAFIELD_KEYS = {
    "set_of",
    "setof",
    "set_of_chairs",
    "chairs_per_set",
    "chair_set_size",
    "quantity",
}


@dataclass(frozen=True)
class ItemEnrichmentRule:
    name: str
    matches: Callable[[dict[str, Any], dict[str, Any]], bool]
    apply: Callable[[dict[str, Any], dict[str, Any], "ShopifyMetafieldResolver"], dict[str, Any]]


class ShopifyMetafieldResolver:
    def __init__(self, integration: ShopifyIntegration):
        self._integration = integration
        self._cache: dict[str, dict[str, str]] = {}

    def get_line_item_metafields(self, line_item: dict[str, Any]) -> dict[str, str]:
        product_id = _normalize_numeric_id(line_item.get("product_id"))
        variant_id = _normalize_numeric_id(line_item.get("variant_id"))

        merged: dict[str, str] = {}
        if variant_id is not None:
            merged.update(self._get_resource_metafields("ProductVariant", variant_id))
        if product_id is not None:
            merged.update(self._get_resource_metafields("Product", product_id))
        return merged

    def _get_resource_metafields(self, resource: str, resource_id: int) -> dict[str, str]:
        cache_key = f"{resource}:{resource_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            data = _post_shopify_graphql(
                integration=self._integration,
                query=GET_RESOURCE_METAFIELDS_QUERY,
                variables={"id": f"gid://shopify/{resource}/{resource_id}"},
            )
        except Exception as exc:
            logger.warning(
                "Failed to fetch Shopify metafields resource=%s id=%s error=%s",
                resource,
                resource_id,
                exc,
            )
            self._cache[cache_key] = {}
            return {}

        node = data.get("node") if isinstance(data, dict) else None
        metafield_nodes = ((node or {}).get("metafields") or {}).get("nodes") or []

        resolved: dict[str, str] = {}
        for metafield in metafield_nodes:
            if not isinstance(metafield, dict):
                continue
            key = metafield.get("key")
            value = metafield.get("value")
            if not isinstance(key, str) or not isinstance(value, str):
                continue
            key_lower = key.strip().lower()
            if not key_lower:
                continue
            resolved[key_lower] = value.strip()

        self._cache[cache_key] = resolved
        return resolved


def enrich_mapped_item_from_shopify_line_item(
    *,
    mapped_item: dict[str, Any],
    line_item: dict[str, Any],
    integration: ShopifyIntegration | None,
    resolver: ShopifyMetafieldResolver | None = None,
) -> dict[str, Any]:
    if not isinstance(mapped_item, dict) or not isinstance(line_item, dict):
        return mapped_item

    if integration is None:
        return mapped_item

    active_resolver = resolver or ShopifyMetafieldResolver(integration)
    item = dict(mapped_item)

    for rule in ITEM_ENRICHMENT_RULES:
        if not rule.matches(item, line_item):
            continue
        try:
            item = rule.apply(item, line_item, active_resolver)
        except Exception as exc:
            logger.warning("Item enrichment rule=%s failed error=%s", rule.name, exc)

    return item


def _matches_chair_item_type(mapped_item: dict[str, Any], _line_item: dict[str, Any]) -> bool:
    item_type = mapped_item.get("item_type")
    return isinstance(item_type, str) and "chair" in item_type.lower()


def _apply_chair_quantity_from_metafields(
    mapped_item: dict[str, Any],
    line_item: dict[str, Any],
    resolver: ShopifyMetafieldResolver,
) -> dict[str, Any]:
    inferred_set_size = _resolve_chair_quantity_from_shopify_metafields(
        line_item=line_item,
        resolver=resolver,
    )
    if inferred_set_size is None:
        return mapped_item

    base_quantity = _coerce_positive_int(mapped_item.get("quantity"))
    if base_quantity is None:
        base_quantity = _coerce_positive_int(line_item.get("quantity"))
    if base_quantity is None:
        base_quantity = 1

    mapped_item["quantity"] = int(base_quantity) * int(inferred_set_size)
    return mapped_item


def _resolve_chair_quantity_from_shopify_metafields(
    *,
    line_item: dict[str, Any],
    resolver: ShopifyMetafieldResolver,
) -> int | None:
    metafields = resolver.get_line_item_metafields(line_item)
    for key in CHAIR_QUANTITY_METAFIELD_KEYS:
        parsed = _parse_positive_int(metafields.get(key))
        if parsed is not None:
            return parsed
    return None


def _normalize_numeric_id(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    parsed = str(value).strip()
    if not parsed.isdigit():
        return None
    return int(parsed)


def _coerce_positive_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        if value.is_integer() and value > 0:
            return int(value)
        return None
    return _parse_positive_int(str(value))


def _parse_positive_int(value: Any) -> int | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.isdigit():
        parsed = int(normalized)
        return parsed if parsed > 0 else None

    match = re.search(r"\d+", normalized)
    if not match:
        return None
    parsed = int(match.group(0))
    return parsed if parsed > 0 else None


def _post_shopify_graphql(
    *,
    integration: ShopifyIntegration,
    query: str,
    variables: dict[str, Any],
) -> dict[str, Any]:
    url = f"https://{integration.shop}/admin/api/{SHOPIFY_ADMIN_API_VERSION}/graphql.json"
    headers = {
        "X-Shopify-Access-Token": integration.access_token,
        "Content-Type": "application/json",
    }
    response = requests.post(
        url,
        json={"query": query, "variables": variables},
        headers=headers,
        timeout=10,
    )
    response.raise_for_status()

    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(f"Shopify GraphQL errors: {payload['errors']}")

    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("Shopify GraphQL response missing data.")
    return data


GET_RESOURCE_METAFIELDS_QUERY = """
query getResourceMetafields($id: ID!) {
  node(id: $id) {
    ... on Product {
      metafields(first: 50) {
        nodes {
          key
          value
        }
      }
    }
    ... on ProductVariant {
      metafields(first: 50) {
        nodes {
          key
          value
        }
      }
    }
  }
}
"""


ITEM_ENRICHMENT_RULES: tuple[ItemEnrichmentRule, ...] = (
    ItemEnrichmentRule(
        name="chair_quantity_from_metafields",
        matches=_matches_chair_item_type,
        apply=_apply_chair_quantity_from_metafields,
    ),
)
