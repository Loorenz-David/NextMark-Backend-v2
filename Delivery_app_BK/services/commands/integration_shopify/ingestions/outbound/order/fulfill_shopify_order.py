from __future__ import annotations

import logging
from typing import Any

import requests

from Delivery_app_BK.models import Order, ShopifyIntegration, db
from Delivery_app_BK.services.domain.order.shopify import should_fulfill_shopify_order


logger = logging.getLogger(__name__)

SHOPIFY_ADMIN_API_VERSION = "2026-04"
GET_ORDER_FULFILLMENT_ORDERS_QUERY = """
query getOrderFulfillmentOrders($orderId: ID!) {
  order(id: $orderId) {
    id
    displayFulfillmentStatus
    fulfillmentOrders(first: 50) {
      nodes {
        id
        status
        requestStatus
        supportedActions {
          action
        }
      }
    }
  }
}
"""

FULFILLMENT_CREATE_MUTATION = """
mutation fulfillmentCreate($fulfillment: FulfillmentInput!, $message: String) {
  fulfillmentCreate(fulfillment: $fulfillment, message: $message) {
    fulfillment {
      id
      status
    }
    userErrors {
      field
      message
    }
  }
}
"""


def fulfill_shopify_order(order_id: int) -> None:
    order = db.session.get(Order, order_id)
    if order is None:
        return
    if not should_fulfill_shopify_order(order):
        return

    integration = (
        db.session.query(ShopifyIntegration)
        .filter(ShopifyIntegration.team_id == order.team_id)
        .order_by(ShopifyIntegration.id.desc())
        .first()
    )
    if integration is None:
        raise RuntimeError(f"No Shopify integration found for team {order.team_id}.")

    fulfillment_order_ids = _get_open_fulfillment_order_ids(order, integration)
    if not fulfillment_order_ids:
        logger.info(
            "No Shopify fulfillment orders eligible for fulfillment | order_id=%s external_order_id=%s",
            getattr(order, "id", None),
            getattr(order, "external_order_id", None),
        )
        return

    _create_fulfillment(
        integration=integration,
        fulfillment_order_ids=fulfillment_order_ids,
    )


def _get_open_fulfillment_order_ids(order: Order, integration: ShopifyIntegration) -> list[str]:
    payload = _post_shopify_graphql(
        integration=integration,
        query=GET_ORDER_FULFILLMENT_ORDERS_QUERY,
        variables={"orderId": _to_shopify_gid("Order", getattr(order, "external_order_id", None))},
    )
    order_payload = payload.get("order") or {}
    fulfillment_orders = ((order_payload.get("fulfillmentOrders") or {}).get("nodes") or [])
    if not isinstance(fulfillment_orders, list):
        return []

    eligible_ids: list[str] = []
    for fulfillment_order in fulfillment_orders:
        if not isinstance(fulfillment_order, dict):
            continue
        fulfillment_order_id = fulfillment_order.get("id")
        if not isinstance(fulfillment_order_id, str) or not fulfillment_order_id.strip():
            continue
        supported_actions = fulfillment_order.get("supportedActions") or []
        if _supports_create_fulfillment(supported_actions):
            eligible_ids.append(fulfillment_order_id)

    return eligible_ids


def _supports_create_fulfillment(supported_actions: Any) -> bool:
    if not isinstance(supported_actions, list):
        return False
    for action_payload in supported_actions:
        if not isinstance(action_payload, dict):
            continue
        action_name = action_payload.get("action")
        if isinstance(action_name, str) and action_name.strip().upper() == "CREATE_FULFILLMENT":
            return True
    return False


def _create_fulfillment(
    *,
    integration: ShopifyIntegration,
    fulfillment_order_ids: list[str],
) -> None:
    _post_shopify_graphql(
        integration=integration,
        query=FULFILLMENT_CREATE_MUTATION,
        variables={
            "fulfillment": {
                "notifyCustomer": False,
                "lineItemsByFulfillmentOrder": [
                    {"fulfillmentOrderId": fulfillment_order_id}
                    for fulfillment_order_id in fulfillment_order_ids
                ],
            }
        },
    )


def _to_shopify_gid(resource_name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise RuntimeError(f"Missing Shopify {resource_name} identifier.")
    normalized = value.strip()
    if not normalized:
        raise RuntimeError(f"Missing Shopify {resource_name} identifier.")
    if normalized.startswith("gid://shopify/"):
        return normalized
    return f"gid://shopify/{resource_name}/{normalized}"


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
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(f"Shopify GraphQL errors: {payload['errors']}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("Shopify GraphQL response missing data.")
    for mutation_name, mutation_payload in data.items():
        user_errors = mutation_payload.get("userErrors") if isinstance(mutation_payload, dict) else None
        if user_errors:
            raise RuntimeError(f"Shopify {mutation_name} userErrors: {user_errors}")
    return data
