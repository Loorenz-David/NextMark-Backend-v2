from Delivery_app_BK.models import db, OrderCase
from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.commands.base.update_instance import update_instance
from Delivery_app_BK.services.commands.utils import extract_targets
from Delivery_app_BK.services.infra.events.emiters import emit_app_events
from Delivery_app_BK.sockets.contracts.realtime import BUSINESS_EVENT_ORDER_CASE_STATE_CHANGED


def update_order_case_state(ctx: ServiceContext):
    instances: list[OrderCase] = []
    for target in extract_targets(ctx):
        state = (target.get("fields") or {}).get("state")
        if state is None:
            raise ValidationFailed("Missing 'state' in fields payload.")
        instance = update_instance(
            ctx,
            OrderCase,
            {"state": state},
            target["target_id"],
        )
        instances.append(instance)
    db.session.commit()
    emit_app_events(ctx, [
        {
            "event_name": BUSINESS_EVENT_ORDER_CASE_STATE_CHANGED,
            "team_id": instance.order.team_id if instance.order else ctx.team_id,
            "entity_type": "order_case",
            "entity_id": instance.id,
            "payload": {
                "order_case_id": instance.id,
                "order_case_client_id": instance.client_id,
                "order_id": instance.order_id,
                "state": instance.state,
            },
            "occurred_at": instance.creation_date,
        }
        for instance in instances
    ])
    return [instance.id for instance in instances]
