"""
Generate and persist tracking identifiers for an order.

Security model:
- A cryptographically random raw token is generated with secrets.token_urlsafe(32).
- Only the SHA-256 hash is stored in the DB (tracking_token_hash).
- The raw token is embedded in the public tracking URL — never stored.

Fields set on the order (mutates in-place, caller must commit):
    tracking_number          — TRK-{order_scalar_id} if set, else TRK-{order.id}
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


def generate_tracking_identifiers(order) -> dict:
    """Populate tracking fields on *order* and return {"raw_token": str}.

    Safe to call multiple times — always regenerates the token (overwrites
    previous values).  Guard against unwanted regeneration on the call site
    with: ``if order.tracking_token_hash is None``.
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)

    # Prefer the human-readable scalar id; fall back to DB pk.
    scalar_id = getattr(order, "order_scalar_id", None) or getattr(order, "id", None)
    order.tracking_number = f"TRK-{scalar_id}"
    order.tracking_token_hash = token_hash
    order.tracking_link = f"{TRACKING_ORDER_BASE_URL}/track/{raw_token}"
    order.tracking_token_created_at = now

    return {"raw_token": raw_token}
