from Delivery_app_BK.models import db, OrderCase, Order, Team, User
from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.commands.base.create_instance import create_instance
from Delivery_app_BK.services.commands.utils import (
    extract_fields,
    build_create_result,
)
from Delivery_app_BK.services.domain.order.order_case_states import OrderCaseState 
from Delivery_app_BK.services.infra.events.emiters import emit_app_events
from Delivery_app_BK.sockets.contracts.realtime import BUSINESS_EVENT_ORDER_CASE_CREATED


def create_order_case(ctx: ServiceContext):
    relationship_map = {
        "team_id": Team,
        "order_id": Order,
        "created_by": User,
    }
    ctx.set_relationship_map(relationship_map)
    instances = []
    user_id = ctx.identity.get('user_id') 

    if not user_id:
        raise NotFound("Could not create a chat because User not found")


    for field_set in extract_fields(ctx):

        if 'order_id' not in field_set:
            raise ValidationFailed("Case must have an order id.")

        if isinstance(user_id, int):
            field_set['created_by'] = user_id

        
        instance: OrderCase = create_instance(ctx, OrderCase, dict(field_set))

       
        if 'state' not in field_set:
            instance.state = OrderCaseState.OPEN.value

        instances.append(instance)

    db.session.add_all(instances)
    db.session.flush()
    result = build_create_result(ctx, instances, extract_fields=['id',"state"])
    db.session.commit()
    emit_app_events(ctx, [
        {
            "event_name": BUSINESS_EVENT_ORDER_CASE_CREATED,
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
    return {"order_case": result}
