from datetime import datetime, timezone

from Delivery_app_BK.models import db, CaseChat, OrderCase, Team, User, NotificationRead
from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.commands.base.create_instance import create_instance
from Delivery_app_BK.services.commands.utils import (
    extract_fields,
    build_create_result,
)
from Delivery_app_BK.services.queries.get_instance import get_instance
from Delivery_app_BK.services.infra.events.emiters import emit_app_events
from Delivery_app_BK.sockets.contracts.realtime import BUSINESS_EVENT_ORDER_CHAT_MESSAGE_CREATED


def create_case_chat(ctx: ServiceContext):
    relationship_map = {
        "team_id": Team,
        "order_case_id": OrderCase,
        "order_case": OrderCase,
        "user_id":User
    }
    ctx.set_relationship_map(relationship_map)
    instances = []

    
    user_id = ctx.identity.get('user_id') 
    
    if not user_id:
        raise NotFound("Could not create a chat because User not found")

    user: User = get_instance(
        ctx=ctx,
        model=User,
        value=user_id,
    )
    resolved_user_name = user.username or user.email

    for field_set in extract_fields(ctx):

        if "order_case_id" not in field_set:
            raise ValidationFailed("Chat must pass an order_case_id")
            
        field_set['user_id'] = user_id
        field_set['user_name'] = resolved_user_name

        
        instance: CaseChat = create_instance(ctx, CaseChat, dict(field_set))
        instances.append(instance)

        if instance.order_case is not None:
            instance.order_case.updated_at = datetime.now(timezone.utc)
        
        notification_read = create_instance(ctx, NotificationRead, {'user_id':user_id})

        instance.notification_reads.append( notification_read )
        

    db.session.add_all(instances)
    db.session.flush()
    result = build_create_result(ctx, instances, extract_fields=['id'])
    db.session.commit()
    emit_app_events(ctx, [
        {
            "event_name": BUSINESS_EVENT_ORDER_CHAT_MESSAGE_CREATED,
            "team_id": instance.order_case.order.team_id if instance.order_case and instance.order_case.order else ctx.team_id,
            "entity_type": "order_chat",
            "entity_id": instance.id,
            "payload": {
                "chat_id": instance.id,
                "chat_client_id": instance.client_id,
                "message": instance.message,
                "order_case_id": instance.order_case_id,
                "order_case_client_id": instance.order_case.client_id if instance.order_case else None,
                "order_id": instance.order_case.order_id if instance.order_case else None,
                "user_id": instance.user_id,
                "user_name": instance.user_name,
            },
            "occurred_at": instance.creation_date,
        }
        for instance in instances
    ])
    return {"case_chat": result}
