from Delivery_app_BK.models import db, CaseChat, NotificationRead, OrderCase, User
from Delivery_app_BK.errors import ValidationFailed

from ...context import ServiceContext
from ...queries.get_instance import get_instance


def mark_order_case_chats_read(ctx: ServiceContext, order_case_id: int):
    if not ctx.user_id:
        raise ValidationFailed("User id is required to mark case chats as read.")

    if not order_case_id:
        raise ValidationFailed("Missing 'order_case_id' in request payload.")

    order_case: OrderCase = get_instance(
        ctx=ctx,
        model=OrderCase,
        value=order_case_id,
    )

    user: User = get_instance(
        ctx=ctx,
        model=User,
        value=ctx.user_id,
    )

    unread_chat_ids = [
        chat_id
        for (chat_id,) in (
            db.session.query(CaseChat.id)
            .filter(
                CaseChat.order_case_id == order_case.id,
                CaseChat.user_id != ctx.user_id,
                ~CaseChat.notification_reads.any(NotificationRead.user_id == ctx.user_id),
            )
            .all()
        )
    ]

    if unread_chat_ids:
        db.session.add_all(
            [
                NotificationRead(
                    reader_name=user.username,
                    user_id=user.id,
                    case_chat_id=chat_id,
                )
                for chat_id in unread_chat_ids
            ]
        )

    db.session.flush()
    db.session.commit()

    return {
        "order_case_read": {
            "order_case_id": order_case.id,
            "marked_count": len(unread_chat_ids),
        }
    }
