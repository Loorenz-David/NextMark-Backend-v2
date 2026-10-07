from __future__ import annotations

from dataclasses import dataclass


INTENT_SKU_TO_PLAN_OBJECTIVE: dict[str, str | None] = {
    "INTENT_LOCAL_DELIVERY": "local_delivery",
    "INTENT_STORE_PICKUP": "store_pickup",
    "INTENT_INTERNATIONAL_SHIPPING": "international_shipping",
    "INTENT_CUSTOMER_TOOK_IT": None,
}

FLAG_SKUS_TO_EXCLUDE: frozenset[str] = frozenset(
    {
        "FLAG_NEEDS_FIXING",
    }
)

DEFAULT_PLAN_OBJECTIVE = "local_delivery"


@dataclass(frozen=True)
class ShopifyIntentResolution:
    plan_objective: str | None
    # The intent maps to no plan objective: the order is kept unplanned.
    is_unplanned: bool


def _normalize_sku(value: object) -> str | None:
    if value is None:
        return None

    normalized = str(value).strip().upper()
    return normalized or None


def resolve_intent_from_shopify_line_items(
    line_items: list[dict],
) -> ShopifyIntentResolution:
    for item in line_items:
        if not isinstance(item, dict):
            continue

        sku = _normalize_sku(item.get("sku"))
        if not sku or sku in FLAG_SKUS_TO_EXCLUDE:
            continue

        if sku not in INTENT_SKU_TO_PLAN_OBJECTIVE:
            continue

        plan_objective = INTENT_SKU_TO_PLAN_OBJECTIVE[sku]
        return ShopifyIntentResolution(
            plan_objective=plan_objective,
            is_unplanned=plan_objective is None,
        )

    return ShopifyIntentResolution(plan_objective=DEFAULT_PLAN_OBJECTIVE, is_unplanned=False)
