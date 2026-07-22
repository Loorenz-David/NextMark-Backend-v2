"""
Generate and persist tracking identifiers for an order.

Security model:
- A cryptographically random raw token is generated with secrets.token_urlsafe(32).
- Only the SHA-256 hash is stored in the DB (tracking_token_hash).
- The raw token is embedded in the public tracking URL — never stored.

Fields set on the order (mutates in-place, caller must commit):
    tracking_number          — cleaned Shopify reference_number when available,
                               otherwise TRK-{order_scalar_id} or TRK-{order.id}
    tracking_token_hash      — sha256(raw_token) hex digest
    tracking_link            — {TRACKING_ORDER_BASE_URL}/track/{raw_token}
    tracking_token_created_at — UTC now

Returns: { "raw_token": str }  (caller may build/log the full URL if needed)
Does NOT commit — the caller is responsible for committing.
"""

import hashlib
import os
import secrets
from datetime import datetime, timezone

TRACKING_ORDER_BASE_URL = os.environ.get(
    "TRACKING_ORDER_BASE_URL", "https://tracking.nextmark.app"
)


def resolve_tracking_number(order) -> str:
    """Resolve the customer-facing tracking number for *order*.

    Shopify references are supplied as values such as ``#5001``.  They are
    used directly after removing ``#`` characters and surrounding whitespace.
    All other orders, and Shopify orders without a usable reference, retain
    the internal ``TRK-<id>`` fallback format.
    """
    if getattr(order, "external_source", None) == "shopify":
        reference_number = getattr(order, "reference_number", None)
        if reference_number is not None:
            cleaned_reference = str(reference_number).replace("#", "").strip()
            if cleaned_reference:
                return cleaned_reference

    scalar_id = getattr(order, "order_scalar_id", None)
    if scalar_id is None:
        scalar_id = getattr(order, "id", None)
    return f"TRK-{scalar_id}"


def generate_tracking_identifiers(order) -> dict:
    """Populate tracking fields on *order* and return {"raw_token": str}.

    Safe to call multiple times — always regenerates the token (overwrites
    previous values).  Guard against unwanted regeneration on the call site
    with: ``if order.tracking_token_hash is None``.
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)

    order.tracking_number = resolve_tracking_number(order)
    order.tracking_token_hash = token_hash
    order.tracking_link = f"{TRACKING_ORDER_BASE_URL}/track/{raw_token}"
    order.tracking_token_created_at = now

    return {"raw_token": raw_token}
