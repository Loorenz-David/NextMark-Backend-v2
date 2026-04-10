from typing import Dict, Any
from sqlalchemy.orm import Query

from Delivery_app_BK.models import db, MessageTemplate
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team
from ....context import ServiceContext
from ...utils import apply_pagination_by_id


def find_message_templates(
    params: Dict[str, Any],
    ctx: ServiceContext,
    query: Query | None = None,
):
    query = query or db.session.query(MessageTemplate)

    # Team scoping
    if model_requires_team(MessageTemplate) and ctx.inject_team_id:
        params = inject_team_id(params, ctx)

    if "team_id" in params:
        query = query.filter(MessageTemplate.team_id == params.get("team_id"))

    # Model-aligned filters
    if "client_id" in params:
        query = query.filter(MessageTemplate.client_id == params.get("client_id"))

    if "name" in params:
        name = params.get("name").strip()
        query = query.filter(MessageTemplate.name.ilike(f"{name}%"))

    if "channel" in params:
        channel = params.get("channel").strip()
        query = query.filter(MessageTemplate.channel == channel)

    if "event" in params:
        query = query.filter(MessageTemplate.event == params.get("event"))

    if "enable" in params:
        query = query.filter(MessageTemplate.enable == params.get("enable"))

    # Sorting
    sort = params.get("sort", "id_desc")
    if sort == "id_asc":
        query = query.order_by(MessageTemplate.id.asc())
    else:
        query = query.order_by(MessageTemplate.id.desc())

    # Pagination
    query = apply_pagination_by_id(
        query,
        id_column=MessageTemplate.id,
        params=params,
        sort=sort,
    )

    return query