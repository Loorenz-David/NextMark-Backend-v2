from typing import Dict, Any
from sqlalchemy.orm import Query, aliased
from sqlalchemy import or_
from Delivery_app_BK.models import db, OrderCase, CaseChat, User,Order
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.utils import apply_pagination_by_date
from Delivery_app_BK.services.utils import (
    inject_team_id,
    model_requires_team,
    to_datetime,
    
)
from Delivery_app_BK.services.queries.utils import (
    parsed_string_to_list
)



def find_order_cases(
    params: Dict[str, Any],
    ctx: ServiceContext,
    query: Query | None = None,
):
    query = query or db.session.query(OrderCase)

    if model_requires_team(OrderCase) and ctx.inject_team_id:
        params = inject_team_id(params, ctx)

    created_by_user_alias = aliased(User)
    user_in_conversation_alias = aliased(User)

    string_filter_map = {
        "created_by_user": {
            "column": created_by_user_alias.username,
            "join": (
                OrderCase.created_by_user.of_type(created_by_user_alias),
            ),
        },
        "user_in_conversation": {
            "column": user_in_conversation_alias.username,
            "join": (
                OrderCase.chats,
                CaseChat.user.of_type(user_in_conversation_alias),
            ),
        },
        "order_reference": {
            "column": Order.reference_number,
            "join": (
                OrderCase.order,
            ),
        },
        "chat": {
            "column": CaseChat.message,
            "join": (
                OrderCase.chats,
            ),
        },
    }

    trimmed_query = str(params.get("q") or "").strip()
    incoming_string_columns = set()

    if "s" in params:
        parsed_list = parsed_string_to_list(params["s"], ctx)
        incoming_string_columns = set(parsed_list)

    if trimmed_query:
        if incoming_string_columns:
            active_columns = incoming_string_columns
        else:
            active_columns = string_filter_map.keys()
    else:
        active_columns = set()

    joined_relations = set()
    search_filters = []

    if trimmed_query and active_columns:
        pattern = f"%{trimmed_query}%"

        for key in active_columns:
            config = string_filter_map.get(key)
            if not config:
                continue

            join_targets = config.get("join") or ()
            for join_target in join_targets:
                if join_target not in joined_relations:
                    query = query.outerjoin(join_target)
                    joined_relations.add(join_target)

            search_filters.append(config["column"].ilike(pattern))

        if search_filters:
            query = query.filter(or_(*search_filters))

        # Avoid duplicated rows when one-to-many joins are active.
        if OrderCase.chats in joined_relations:
            query = query.distinct()

    if "team_id" in params:
        query = query.filter(OrderCase.team_id == params.get("team_id"))

    if "order_id" in params:
        order_ids = params.get("order_id")
        if not isinstance(order_ids, (list, tuple)):
            order_ids = [order_ids]
        query = query.filter(OrderCase.order_id.in_(order_ids))

   
   
    if "creation_date_from" in params:
        creation_date_from = to_datetime(params.get("creation_date_from"))
        query = query.filter(OrderCase.creation_date >= creation_date_from)

    if "creation_date_to" in params:
        creation_date_to = to_datetime(params.get("creation_date_to"))
        query = query.filter(OrderCase.creation_date <= creation_date_to)

    if params.get("sort") == "date_asc":
        query = query.order_by(OrderCase.creation_date.asc(), OrderCase.id.asc())
    else:
        query = query.order_by(OrderCase.creation_date.desc(), OrderCase.id.desc())

    query = apply_pagination_by_date(
        query=query,
        date_column=OrderCase.creation_date,
        id_column=OrderCase.id,
        params=params,
        sort=params.get("sort", "date_desc"),
    )

    return query
