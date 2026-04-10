from Delivery_app_BK.models import db, OrderCase, Order, Team, User
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.commands.base.update_instance import update_instance
from Delivery_app_BK.services.commands.utils import extract_targets
from Delivery_app_BK.services.infra.events.emiters import emit_app_events
from Delivery_app_BK.sockets.contracts.realtime import BUSINESS_EVENT_ORDER_CASE_UPDATED


def update_order_case(ctx: ServiceContext):
    relationship_map = {
        "team_id": Team,
        "order_id": Order,
        "created_by": User,
    }
    ctx.set_relationship_map(relationship_map)
    instances = []
    for target in extract_targets(ctx):
        instance = update_instance(
            ctx, OrderCase, target["fields"], target["target_id"]
        )
        instances.append((instance, list((target.get("fields") or {}).keys())))
    db.session.commit()
    emit_app_events(ctx, [
        {
            "event_name": BUSINESS_EVENT_ORDER_CASE_UPDATED,
            "team_id": instance.order.team_id if instance.order else ctx.team_id,
            "entity_type": "order_case",
            "entity_id": instance.id,
            "payload": {
                "order_case_id": instance.id,
                "order_case_client_id": instance.client_id,
                "order_id": instance.order_id,
                "state": instance.state,
                "changed_fields": changed_fields,
            },
            "occurred_at": instance.creation_date,
        }
        for instance, changed_fields in instances
    ])
    return [instance.id for instance, _ in instances]
