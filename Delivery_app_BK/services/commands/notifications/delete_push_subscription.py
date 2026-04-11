from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import PushSubscription, db

from ...context import ServiceContext


def delete_push_subscription(ctx: ServiceContext) -> dict:
    if not ctx.user_id:
        raise ValidationFailed("Authentication required.")

    endpoint: str | None = ctx.incoming_data.get("endpoint")
    if not endpoint:
        raise ValidationFailed("Missing 'endpoint' in request payload.")

    subscription: PushSubscription | None = PushSubscription.query.filter_by(
        endpoint=endpoint,
        user_id=ctx.user_id,
    ).first()

    if subscription:
        db.session.delete(subscription)
        db.session.commit()

    return {}
