import json
from datetime import datetime, timezone

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import PushSubscription, db

from ...context import ServiceContext


def upsert_push_subscription(ctx: ServiceContext) -> dict:
    if not ctx.user_id:
        raise ValidationFailed("Authentication required.")

    data = ctx.incoming_data
    endpoint: str | None = data.get("endpoint")
    keys: dict = data.get("keys") or {}
    p256dh: str | None = keys.get("p256dh")
    auth: str | None = keys.get("auth")

    if not endpoint:
        raise ValidationFailed("Missing 'endpoint' in request payload.")
    if not p256dh or not auth:
        raise ValidationFailed("Missing 'keys.p256dh' or 'keys.auth' in request payload.")

    expiration_time = data.get("expirationTime")
    user_agent: str | None = data.get("userAgent")
    raw_subscription = data.get("subscription")
    subscription_json: str | None = json.dumps(raw_subscription) if raw_subscription else None

    now = datetime.now(timezone.utc)

    existing: PushSubscription | None = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if existing:
        existing.user_id = ctx.user_id
        existing.p256dh = p256dh
        existing.auth = auth
        existing.expiration_time = str(expiration_time) if expiration_time is not None else None
        existing.subscription_json = subscription_json
        existing.user_agent = user_agent
        existing.is_active = True
        existing.last_seen_at = now
        existing.updated_at = now
    else:
        subscription = PushSubscription(
            user_id=ctx.user_id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
            expiration_time=str(expiration_time) if expiration_time is not None else None,
            subscription_json=subscription_json,
            user_agent=user_agent,
            is_active=True,
            last_seen_at=now,
            created_at=now,
            updated_at=now,
        )
        db.session.add(subscription)

    db.session.commit()
    return {}
