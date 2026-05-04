from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Callable

import requests

from Delivery_app_BK.models import ShopifyIntegration


logger = logging.getLogger(__name__)

SHOPIFY_ADMIN_API_VERSION = "2026-04"
SHOPIFY_GRAPHQL_NODES_BATCH_SIZE = 200
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


class ShopifyLineItemMediaResolver:
    def __init__(self, integration: ShopifyIntegration, line_items: list[dict[str, Any]]):
        self._integration = integration
        self._line_items = list(line_items or [])
        self._loaded = False
        self._variant_images: dict[int, list[str]] = {}
        self._product_images: dict[int, list[str]] = {}
        self._variant_page_links: dict[int, str] = {}
        self._product_page_links: dict[int, str] = {}

    def get_line_item_images(self, line_item: dict[str, Any]) -> list[str]:
        if not isinstance(line_item, dict):
            return []
        self._ensure_loaded()

        variant_id = _normalize_numeric_id(line_item.get("variant_id"))
        product_id = _normalize_numeric_id(line_item.get("product_id"))

        if variant_id is not None:
            variant_images = self._variant_images.get(variant_id) or []
            if variant_images:
                return list(variant_images)

        if product_id is not None:
            product_images = self._product_images.get(product_id) or []
            if product_images:
                return list(product_images)

        return []

    def get_line_item_page_link(self, line_item: dict[str, Any]) -> str | None:
        if not isinstance(line_item, dict):
            return None
        self._ensure_loaded()

        variant_id = _normalize_numeric_id(line_item.get("variant_id"))
        product_id = _normalize_numeric_id(line_item.get("product_id"))

        if variant_id is not None:
            variant_page_link = self._variant_page_links.get(variant_id)
            if variant_page_link:
                return variant_page_link

        if product_id is not None:
            product_page_link = self._product_page_links.get(product_id)
            if product_page_link:
                return product_page_link

        return None

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True

        ids = _line_item_product_and_variant_gids(self._line_items)
        if not ids:
            return

        nodes: list[Any] = []
        for batch in _chunked(ids, SHOPIFY_GRAPHQL_NODES_BATCH_SIZE):
            try:
                data = _post_shopify_graphql(
                    integration=self._integration,
                    query=GET_LINE_ITEM_IMAGE_NODES_QUERY,
                    variables={"ids": batch},
                )
            except Exception as exc:
                logger.warning("Failed to fetch Shopify line item images error=%s", exc)
                continue

            batch_nodes = data.get("nodes") if isinstance(data, dict) else None
            if isinstance(batch_nodes, list):
                nodes.extend(batch_nodes)

        for node in nodes:
            if not isinstance(node, dict):
                continue
            gid = node.get("id")
            resource, numeric_id = _parse_shopify_gid(gid)
            if numeric_id is None:
                continue

            if resource == "ProductVariant":
                images = _variant_image_urls(node)
                if images:
                    self._variant_images[numeric_id] = images
                page_link = _variant_page_link(node, self._integration)
                if page_link:
                    self._variant_page_links[numeric_id] = page_link
            elif resource == "Product":
                images = _product_image_urls(node)
                if images:
                    self._product_images[numeric_id] = images
                page_link = _product_page_link(node, self._integration)
                if page_link:
                    self._product_page_links[numeric_id] = page_link


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


def apply_shopify_line_item_images(
    *,
    mapped_item: dict[str, Any],
    line_item: dict[str, Any],
    resolver: ShopifyLineItemMediaResolver | None,
) -> dict[str, Any]:
    if not isinstance(mapped_item, dict) or not isinstance(line_item, dict):
        return mapped_item
    if resolver is None:
        return mapped_item

    images = resolver.get_line_item_images(line_item)
    if not images:
        return mapped_item

    item = dict(mapped_item)
    item["item_images"] = images
    return item


def apply_shopify_line_item_media(
    *,
    mapped_item: dict[str, Any],
    line_item: dict[str, Any],
    resolver: ShopifyLineItemMediaResolver | None,
) -> dict[str, Any]:
    if not isinstance(mapped_item, dict) or not isinstance(line_item, dict):
        return mapped_item
    if resolver is None:
        return mapped_item

    images = resolver.get_line_item_images(line_item)
    page_link = resolver.get_line_item_page_link(line_item)
    if not images and not page_link:
        return mapped_item

    item = dict(mapped_item)
    if images:
        item["item_images"] = images
    if page_link:
        item["page_link"] = page_link
    return item


def _matches_chair_item_type(mapped_item: dict[str, Any], _line_item: dict[str, Any]) -> bool:
    item_type = mapped_item.get("item_type")
    return isinstance(item_type, str) and "chair" in item_type.lower()


ShopifyLineItemImageResolver = ShopifyLineItemMediaResolver


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


def _line_item_product_and_variant_gids(line_items: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    ids: list[str] = []

    for line_item in line_items:
        if not isinstance(line_item, dict):
            continue

        variant_id = _normalize_numeric_id(line_item.get("variant_id"))
        if variant_id is not None:
            gid = f"gid://shopify/ProductVariant/{variant_id}"
            if gid not in seen:
                seen.add(gid)
                ids.append(gid)

        product_id = _normalize_numeric_id(line_item.get("product_id"))
        if product_id is not None:
            gid = f"gid://shopify/Product/{product_id}"
            if gid not in seen:
                seen.add(gid)
                ids.append(gid)

    return ids


def _parse_shopify_gid(value: Any) -> tuple[str | None, int | None]:
    if not isinstance(value, str):
        return None, None
    parts = value.rstrip("/").split("/")
    if len(parts) < 2:
        return None, None
    resource = parts[-2]
    numeric_id = _normalize_numeric_id(parts[-1])
    return resource, numeric_id


def _variant_image_urls(node: dict[str, Any]) -> list[str]:
    image = node.get("image")
    url = _image_url(image)
    return [url] if url else []


def _product_image_urls(node: dict[str, Any]) -> list[str]:
    resolved: list[str] = []

    featured_media = node.get("featuredMedia")
    featured_url = _image_url(((featured_media or {}).get("preview") or {}).get("image"))
    if featured_url:
        resolved.append(featured_url)

    image_nodes = ((node.get("images") or {}).get("nodes")) or []
    for image in image_nodes:
        url = _image_url(image)
        if url and url not in resolved:
            resolved.append(url)

    return resolved


def _image_url(image: Any) -> str | None:
    if not isinstance(image, dict):
        return None
    url = image.get("url") or image.get("originalSrc") or image.get("src")
    if not isinstance(url, str):
        return None
    normalized = url.strip()
    return normalized or None


def _variant_page_link(node: dict[str, Any], integration: ShopifyIntegration) -> str | None:
    product = node.get("product")
    page_link = _product_page_link(product, integration)
    variant_id = _normalize_numeric_id(_parse_shopify_gid(node.get("id"))[1])
    if not page_link or variant_id is None:
        return page_link
    separator = "&" if "?" in page_link else "?"
    return f"{page_link}{separator}variant={variant_id}"


def _product_page_link(node: Any, integration: ShopifyIntegration) -> str | None:
    if not isinstance(node, dict):
        return None

    online_store_url = node.get("onlineStoreUrl")
    if isinstance(online_store_url, str) and online_store_url.strip():
        return online_store_url.strip()

    handle = node.get("handle")
    if not isinstance(handle, str) or not handle.strip():
        return None

    shop = getattr(integration, "shop", None)
    if not isinstance(shop, str) or not shop.strip():
        return None

    return f"https://{shop.strip().rstrip('/')}/products/{handle.strip()}"


def _chunked(values: list[str], size: int) -> list[list[str]]:
    if size <= 0:
        return [values]
    return [values[index:index + size] for index in range(0, len(values), size)]


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


GET_LINE_ITEM_IMAGE_NODES_QUERY = """
query getLineItemImages($ids: [ID!]!) {
  nodes(ids: $ids) {
    id
    ... on ProductVariant {
      image {
        url
      }
      product {
        onlineStoreUrl
        handle
      }
    }
    ... on Product {
      onlineStoreUrl
      handle
      featuredMedia {
        preview {
          image {
            url
          }
        }
      }
      images(first: 10) {
        nodes {
          url
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
