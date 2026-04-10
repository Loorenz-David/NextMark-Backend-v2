"""
Generate a secure client-form token for an order.

Security model:
- A cryptographically random raw token is generated with secrets.token_urlsafe(32).
- The SHA-256 hash is stored in the DB (client_form_token_hash).
- The raw token is also stored encrypted (client_form_token_encrypted) to support
    safe resend of still-valid links.
- Regenerating clears client_form_submitted_at so the new token is single-use.

Returns: { "raw_token": str, "expires_at": datetime, "order": Order }
  Caller builds the full URL as: f"{BASE_URL}/form/{raw_token}"
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from Delivery_app_BK.models import db, Order
from Delivery_app_BK.errors import NotFound
from Delivery_app_BK.services.utils.crypto import decrypt_secret, encrypt_secret


DEFAULT_TTL_HOURS = 72
DEFAULT_CLIENT_FORM_BASE_URL = os.environ.get("CLIENT_FORM_BASE_URL", "https://forms.nextmark.app")


def _load_order(order_id: int, team_id: int) -> Order:
    order: Order | None = (
        db.session.query(Order)
        .filter(Order.id == order_id, Order.team_id == team_id)
        .first()
    )

    if order is None:
        raise NotFound(f"Order {order_id} not found.")

    return order


def _is_reusable_token(order: Order) -> bool:
    expires_at = order.client_form_token_expires_at
    if not order.client_form_token_hash or not order.client_form_token_encrypted:
        return False
    if order.client_form_submitted_at is not None:
        return False
    if expires_at is None or datetime.now(timezone.utc) > expires_at:
        return False
    return True


def _extract_valid_raw_token(order: Order) -> str | None:
    if not _is_reusable_token(order):
        return None

    try:
        raw_token = decrypt_secret(order.client_form_token_encrypted)
    except Exception:
        return None

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    if token_hash != order.client_form_token_hash:
        return None

    return raw_token


def get_existing_client_form_url(order: Order, *, base_url: str = DEFAULT_CLIENT_FORM_BASE_URL) -> str | None:
    raw_token = _extract_valid_raw_token(order)
    if not raw_token:
        return None
    return f"{base_url}/form/{raw_token}"


def generate_client_form_token(order_id: int, team_id: int, ttl_hours: int = DEFAULT_TTL_HOURS) -> dict:
    order = _load_order(order_id, team_id)

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

    order.client_form_token_hash = token_hash
    order.client_form_token_encrypted = encrypt_secret(raw_token)
    order.client_form_token_expires_at = expires_at
    order.client_form_submitted_at = None   # reset previous submission on regenerate

    db.session.commit()

    return {
        "raw_token": raw_token,
        "expires_at": order.client_form_token_expires_at,
        "order": order,
    }


def get_or_generate_client_form_token(order_id: int, team_id: int, ttl_hours: int = DEFAULT_TTL_HOURS) -> dict:
    order = _load_order(order_id, team_id)
    raw_token = _extract_valid_raw_token(order)
    if raw_token is not None:
        return {
            "raw_token": raw_token,
            "expires_at": order.client_form_token_expires_at,
            "order": order,
            "reused": True,
        }

    generated = generate_client_form_token(order_id, team_id, ttl_hours=ttl_hours)
    generated["reused"] = False
    return generated
