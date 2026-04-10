from Delivery_app_BK.models import db, CaseChat, NotificationRead, User
from Delivery_app_BK.errors import ValidationFailed

from ...context import ServiceContext
from ..base.create_instance import create_instance
from ..utils import extract_fields, build_create_result
from ...queries.get_instance import get_instance


def create_notification_read(ctx: ServiceContext, order_chat_id:int):
    if not ctx.user_id:
        raise ValidationFailed("User id is required to create a notification read.")

    if not order_chat_id:
        raise ValidationFailed("Missing 'order_chat_id' in request payload.")

    order_chat: CaseChat = get_instance(
        ctx=ctx,
        model=CaseChat,
        value=order_chat_id,
    )
    user: User = get_instance(
        ctx = ctx,
        model = User,
        value = ctx.user_id
    )

        
    instance = NotificationRead(
        reader_name = user.username,
        user_id = user.id,
    )


    order_chat.notification_reads.append(instance)


    db.session.add(instance)
    db.session.flush()
    result = build_create_result(ctx, [instance] )
    db.session.commit()

    return {"notification_read": result}
