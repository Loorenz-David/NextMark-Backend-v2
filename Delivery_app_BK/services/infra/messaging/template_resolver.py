from __future__ import annotations

from Delivery_app_BK.models import MessageTemplate, db


def resolve_message_template(
    *,
    team_id: int | None,
    channel: str,
    event_name: str,
    plan_type: str,
    enabled_only: bool = False,
) -> MessageTemplate | None:
    """
    The single template lookup every sender goes through. There is no
    fallback across plan types on purpose: a missing or disabled pickup
    template means no pickup message, never the delivery one.
    """
    if team_id is None:
        return None

    query = db.session.query(MessageTemplate).filter(
        MessageTemplate.team_id == team_id,
        MessageTemplate.channel == channel,
        MessageTemplate.event == event_name,
        MessageTemplate.plan_type == plan_type,
    )
    if enabled_only:
        query = query.filter(MessageTemplate.enable.is_(True))

    return query.first()
