from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import phonenumbers
import requests
from sqlalchemy.orm import selectinload

from Delivery_app_BK.models import Costumer, Order, ShopifyIntegration, db
from Delivery_app_BK.services.domain.order.shopify import (
    SHOPIFY_EXTERNAL_SOURCE,
    is_shopify_order,
    should_sync_shopify_order_costumer,
)


logger = logging.getLogger(__name__)

SHOPIFY_ADMIN_API_VERSION = "2026-04"
CUSTOMER_SET_MUTATION = """
mutation customerSet($input: CustomerSetInput!, $identifier: CustomerSetIdentifiers) {
  customerSet(input: $input, identifier: $identifier) {
    customer {
      id
    }
    userErrors {
      field
      message
    }
  }
}
"""

ORDER_CUSTOMER_SET_MUTATION = """
mutation orderCustomerSet($orderId: ID!, $customerId: ID!) {
  orderCustomerSet(orderId: $orderId, customerId: $customerId) {
    order {
      id
      customer {
        id
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

CUSTOMER_EMAIL_MARKETING_CONSENT_UPDATE_MUTATION = """
mutation customerEmailMarketingConsentUpdate($input: CustomerEmailMarketingConsentUpdateInput!) {
  customerEmailMarketingConsentUpdate(input: $input) {
    customer {
      id
    }
    userErrors {
      field
      message
    }
  }
}
"""


def sync_order_costumer_to_shopify(order_id: int) -> None:
    order = (
        db.session.query(Order)
        .options(
            selectinload(Order.costumer).selectinload(Costumer.addresses),
            selectinload(Order.costumer).selectinload(Costumer.phones),
        )
        .filter(Order.id == order_id)
        .first()
    )
    if order is None:
        logger.warning("[shopify-costumer-sync] sync: order not found order_id=%s", order_id)
        return

    _costumer = order.costumer
    logger.info(
        "[shopify-costumer-sync] sync: loaded order_id=%s external_source=%s "
        "external_order_id=%s costumer_id=%s costumer_external_source=%s "
        "costumer_external_costumer_id=%s",
        order_id,
        getattr(order, "external_source", None),
        getattr(order, "external_order_id", None),
        getattr(_costumer, "id", None),
        getattr(_costumer, "external_source", None),
        getattr(_costumer, "external_costumer_id", None),
    )

    if not should_sync_shopify_order_costumer(order, _build_submitted_fields_snapshot(order)):
        logger.warning(
            "[shopify-costumer-sync] sync: SKIPPED by guard order_id=%s "
            "(is_shopify_order=%s costumer_present=%s)",
            order_id,
            is_shopify_order(order),
            _costumer is not None,
        )
        return

    integration = (
        db.session.query(ShopifyIntegration)
        .filter(ShopifyIntegration.team_id == order.team_id)
        .order_by(ShopifyIntegration.id.desc())
        .first()
    )
    if integration is None:
        raise RuntimeError(f"No Shopify integration found for team {order.team_id}.")

    logger.info(
        "[shopify-costumer-sync] sync: integration found id=%s shop=%s scopes=%s order_id=%s",
        integration.id,
        integration.shop,
        getattr(integration, "scopes", None),
        order_id,
    )

    customer_gid = _ensure_shopify_customer(order, integration)
    logger.info(
        "[shopify-costumer-sync] sync: customerSet OK customer_gid=%s order_id=%s",
        customer_gid,
        order_id,
    )
    _sync_email_marketing_consent(order, integration, customer_gid)
    _assign_shopify_customer_to_order(order, integration, customer_gid)
    logger.info(
        "[shopify-costumer-sync] sync: orderCustomerSet OK order_id=%s", order_id
    )

    costumer = order.costumer
    if costumer is not None:
        costumer.external_source = SHOPIFY_EXTERNAL_SOURCE
        costumer.external_costumer_id = _to_external_resource_id(customer_gid)
        db.session.add(costumer)
        db.session.commit()
        logger.info(
            "[shopify-costumer-sync] sync: costumer stamped costumer_id=%s "
            "external_costumer_id=%s order_id=%s",
            costumer.id,
            costumer.external_costumer_id,
            order_id,
        )


def _build_submitted_fields_snapshot(order: Order) -> dict[str, Any]:
    return {
        "client_first_name": order.client_first_name,
        "client_last_name": order.client_last_name,
        "client_email": order.client_email,
        "client_primary_phone": order.client_primary_phone,
        "client_secondary_phone": order.client_secondary_phone,
        "client_address": order.client_address,
        "marketing_messages": order.marketing_messages,
    }


def _ensure_shopify_customer(order: Order, integration: ShopifyIntegration) -> str:
    costumer = order.costumer
    payload = _build_customer_set_payload(order, costumer)
    result = _post_shopify_graphql(
        integration=integration,
        query=CUSTOMER_SET_MUTATION,
        variables=payload,
    )
    customer_data = ((result.get("customerSet") or {}).get("customer") or {})
    customer_id = customer_data.get("id")
    if not isinstance(customer_id, str) or not customer_id.strip():
        raise RuntimeError("Shopify customerSet did not return a customer id.")
    return customer_id


def _sync_email_marketing_consent(
    order: Order,
    integration: ShopifyIntegration,
    customer_gid: str,
) -> None:
    """Push the order's email marketing consent to the Shopify customer.

    No-op when ``marketing_messages`` is None/unavailable (never treated as an
    unsubscribe) or when the customer has no email. Errors from Shopify propagate
    and fail the command, matching the rest of the sync. Idempotent: re-running
    with the same boolean lands Shopify in the same subscription state.
    """
    variables = _build_email_marketing_consent_variables(order, customer_gid)
    if variables is None:
        logger.info(
            "[shopify-costumer-sync] consent: skipped (no marketing value or email) order_id=%s",
            getattr(order, "id", None),
        )
        return

    _post_shopify_graphql(
        integration=integration,
        query=CUSTOMER_EMAIL_MARKETING_CONSENT_UPDATE_MUTATION,
        variables=variables,
    )
    logger.info(
        "[shopify-costumer-sync] consent: %s applied customer_gid=%s order_id=%s",
        variables["input"]["emailMarketingConsent"]["marketingState"],
        customer_gid,
        getattr(order, "id", None),
    )


def _build_email_marketing_consent_variables(
    order: Order,
    customer_gid: str,
) -> dict[str, Any] | None:
    marketing_messages = getattr(order, "marketing_messages", None)
    if marketing_messages is None:
        return None

    email = _resolve_customer_email(order, getattr(order, "costumer", None))
    if not email:
        return None

    consent: dict[str, Any] = {
        "marketingState": "SUBSCRIBED" if marketing_messages else "UNSUBSCRIBED",
        "consentUpdatedAt": datetime.now(timezone.utc).isoformat(),
    }
    if marketing_messages:
        consent["marketingOptInLevel"] = "SINGLE_OPT_IN"

    return {
        "input": {
            "customerId": customer_gid,
            "emailMarketingConsent": consent,
        }
    }


def _assign_shopify_customer_to_order(
    order: Order,
    integration: ShopifyIntegration,
    customer_gid: str,
) -> None:
    _post_shopify_graphql(
        integration=integration,
        query=ORDER_CUSTOMER_SET_MUTATION,
        variables={
            "orderId": _to_shopify_gid("Order", getattr(order, "external_order_id", None)),
            "customerId": customer_gid,
        },
    )


def _resolve_customer_email(order: Order, costumer: Costumer | None) -> str | None:
    # Prefer the value submitted on the order (the freshly filled client form)
    # over the stored costumer entity, which may still hold placeholder data.
    return _pick_first_non_empty(
        getattr(order, "client_email", None),
        getattr(costumer, "email", None),
    )


def _build_customer_set_payload(order: Order, costumer: Costumer | None) -> dict[str, Any]:
    # Prefer the values submitted on the order (the freshly filled client form)
    # over the stored costumer entity, which may still hold placeholder data
    # created during inbound ingestion. Phone and address already do this.
    email = _resolve_customer_email(order, costumer)
    phone = _build_phone_string(
        getattr(order, "client_primary_phone", None)
        or _extract_default_phone(costumer)
    )
    # Prefer the known Shopify customer id so an edit that changes the email or
    # phone still updates the SAME customer instead of creating a duplicate.
    existing_external_id = getattr(costumer, "external_costumer_id", None)
    identifier: dict[str, str] | None = None
    if existing_external_id:
        identifier = {"id": _to_shopify_gid("Customer", str(existing_external_id))}
    elif email:
        identifier = {"email": email}
    elif phone:
        identifier = {"phone": phone}

    first_name = _pick_first_non_empty(
        getattr(order, "client_first_name", None),
        getattr(costumer, "first_name", None),
        "Shopify",
    )
    last_name = _pick_first_non_empty(
        getattr(order, "client_last_name", None),
        getattr(costumer, "last_name", None),
        "Customer",
    )

    input_payload: dict[str, Any] = {
        "firstName": first_name,
        "lastName": last_name,
    }
    if email:
        input_payload["email"] = email
    if phone:
        input_payload["phone"] = phone

    mailing_address = _build_mailing_address(order, costumer, phone, first_name, last_name)
    if mailing_address:
        input_payload["addresses"] = [mailing_address]

    payload = {"input": input_payload}
    if identifier is not None:
        payload["identifier"] = identifier
    return payload


def _build_mailing_address(
    order: Order,
    costumer: Costumer | None,
    phone: str | None,
    first_name: str,
    last_name: str,
) -> dict[str, Any] | None:
    address = getattr(order, "client_address", None) or _extract_default_address(costumer)
    if not isinstance(address, dict):
        return None

    payload: dict[str, Any] = {
        "address1": address.get("street_address"),
        "city": address.get("city"),
        "zip": address.get("postal_code"),
        "firstName": first_name,
        "lastName": last_name,
    }
    if phone:
        payload["phone"] = phone
    country_code = _normalize_country_code(address.get("country"))
    if country_code:
        payload["countryCode"] = country_code
    province_code = address.get("state")
    if isinstance(province_code, str) and province_code.strip():
        payload["provinceCode"] = province_code.strip()

    cleaned = {key: value for key, value in payload.items() if isinstance(value, str) and value.strip()}
    return cleaned or None


def _extract_default_address(costumer: Costumer | None) -> dict[str, Any] | None:
    if costumer is None:
        return None
    default_id = getattr(costumer, "default_address_id", None)
    for address in list(getattr(costumer, "addresses", None) or []):
        if getattr(address, "id", None) == default_id and isinstance(getattr(address, "address", None), dict):
            return address.address
    return None


def _extract_default_phone(costumer: Costumer | None) -> dict[str, Any] | None:
    if costumer is None:
        return None
    default_id = getattr(costumer, "default_primary_phone_id", None)
    for phone in list(getattr(costumer, "phones", None) or []):
        if getattr(phone, "id", None) == default_id and isinstance(getattr(phone, "phone", None), dict):
            return phone.phone
    return None


def _build_phone_string(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    prefix = value.get("prefix")
    number = value.get("number")
    if not (isinstance(prefix, str) and isinstance(number, str) and prefix.strip() and number.strip()):
        return None

    prefix = prefix.strip()
    if not prefix.startswith("+"):
        prefix = "+" + prefix.lstrip("+")
    candidate = f"{prefix}{number.strip()}"

    # Shopify rejects the entire customerSet mutation on an invalid phone, so
    # normalize to E.164 and drop it if it cannot be validated rather than let
    # one bad field block the whole customer update.
    try:
        parsed = phonenumbers.parse(candidate, None)
    except phonenumbers.NumberParseException:
        logger.warning("[shopify-costumer-sync] dropping unparseable phone %r", candidate)
        return None
    if not phonenumbers.is_valid_number(parsed):
        logger.warning("[shopify-costumer-sync] dropping invalid phone %r", candidate)
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def _normalize_country_code(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    if len(normalized) == 2 and normalized.isalpha():
        return normalized
    return None


def _pick_first_non_empty(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _to_shopify_gid(resource_name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise RuntimeError(f"Missing Shopify {resource_name} identifier.")
    normalized = value.strip()
    if not normalized:
        raise RuntimeError(f"Missing Shopify {resource_name} identifier.")
    if normalized.startswith("gid://shopify/"):
        return normalized
    return f"gid://shopify/{resource_name}/{normalized}"


def _to_external_resource_id(gid: str) -> str:
    if not isinstance(gid, str):
        return ""
    if gid.startswith("gid://shopify/"):
        return gid.rsplit("/", 1)[-1]
    return gid


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
    if response.status_code >= 400:
        logger.error(
            "[shopify-costumer-sync] graphql HTTP error status=%s url=%s body=%s",
            response.status_code,
            url,
            response.text[:1000],
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
