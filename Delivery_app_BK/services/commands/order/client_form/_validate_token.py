"""
Shared helper: hash a raw token, look up the order, and validate expiry + single-use.

Raises:
    TokenInvalidError  — no order found for the given token hash
    TokenExpiredError  — the token's TTL has elapsed
    TokenAlreadyUsedError — the form was already submitted
"""

import hashlib
from datetime import datetime, timezone

from sqlalchemy.orm import joinedload

from Delivery_app_BK.models import db, Order
from Delivery_app_BK.errors import TokenInvalidError, TokenExpiredError, TokenAlreadyUsedError


def validate_and_get_order(token: str) -> Order:
    """Hash *token*, find the matching Order, and validate expiry + single-use.

    Returns the Order instance on success.
    Raises one of the three TokenError sub-classes on failure.
    """
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    order: Order | None = (
        db.session.query(Order)
        .options(joinedload(Order.delivery_plan))
        .filter(Order.client_form_token_hash == token_hash)
        .first()
    )

    if order is None:
        raise TokenInvalidError()

    # Treat a missing expiry as an expired token (defensive guard for bad data).
    if order.client_form_token_expires_at is None or datetime.now(timezone.utc) > order.client_form_token_expires_at:
        raise TokenExpiredError()

    if order.client_form_submitted_at is not None:
        raise TokenAlreadyUsedError()

    return order
