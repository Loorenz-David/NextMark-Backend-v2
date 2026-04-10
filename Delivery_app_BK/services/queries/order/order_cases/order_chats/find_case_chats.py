from typing import Dict, Any
from sqlalchemy.orm import Query

from Delivery_app_BK.models import db, CaseChat, OrderCase
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.utils import apply_pagination_by_date
from Delivery_app_BK.services.utils import (
    inject_team_id,
    model_requires_team,
    to_datetime,
)


def find_case_chats(
    params: Dict[str, Any],
    ctx: ServiceContext,
    query: Query | None = None,
):
    query = query or db.session.query(CaseChat)

    if model_requires_team(CaseChat) and ctx.inject_team_id:
        params = inject_team_id( params, ctx )
    
    if "team_id" in params:
        query = query.filter(CaseChat.team_id == params.get("team_id"))


    if "order_case_id" in params:
        case_ids = params.get("order_case_id")
        if not isinstance(case_ids, (list, tuple)):
            case_ids = [case_ids]
        query = query.filter(CaseChat.order_case_id.in_(case_ids))

    if "order_id" in params:
        order_ids = params.get("order_id")
        if not isinstance(order_ids, (list, tuple)):
            order_ids = [order_ids]
        query = query.join(OrderCase).filter(OrderCase.order_id.in_(order_ids))

    if "user_id" in params:
        user_ids = params.get("user_id")
        if not isinstance(user_ids, (list, tuple)):
            user_ids = [user_ids]
        query = query.filter(CaseChat.user_id.in_(user_ids))

    if "creation_date_from" in params:
        creation_date_from = to_datetime(params.get("creation_date_from"))
        query = query.filter(CaseChat.creation_date >= creation_date_from)

    if "creation_date_to" in params:
        creation_date_to = to_datetime(params.get("creation_date_to"))
        query = query.filter(CaseChat.creation_date <= creation_date_to)

    if params.get("sort") == "date_asc":
        query = query.order_by(CaseChat.creation_date.asc(), CaseChat.id.asc())
    else:
        query = query.order_by(CaseChat.creation_date.desc(), CaseChat.id.desc())

    query = apply_pagination_by_date(
        query=query,
        date_column=CaseChat.creation_date,
        id_column=CaseChat.id,
        params=params,
        sort=params.get("sort", "date_desc"),
    )

    return query
