from typing import Dict, Any
from sqlalchemy.orm import Query
from sqlalchemy import or_

from Delivery_app_BK.models import db, ItemState
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team

from ...context import ServiceContext
from ..utils import apply_pagination_by_id
from ..utils.format_data import str_to_bool


def find_item_states(
    params: Dict[str, Any],
    ctx: ServiceContext,
    query: Query | None = None,
):
    query = query or db.session.query(ItemState)

    if model_requires_team(ItemState) and ctx.inject_team_id:
        params = inject_team_id(params, ctx)


    include_defaults = False
    if "include_defaults" in params:
        include_defaults = str_to_bool(params.get("include_defaults"))

    if "team_id" in params:
        if include_defaults:
            query = query.filter(
                or_(
                    ItemState.is_system.is_(True),
                    ItemState.default.is_(True),
                    ItemState.team_id == params["team_id"],
                )
            )
        else:
            query = query.filter(
                or_(
                    ItemState.is_system.is_(True),
                    ItemState.team_id == params["team_id"],
                )
            )
    elif include_defaults:
        query = query.filter(
            or_(
                ItemState.is_system.is_(True),
                ItemState.default.is_(True),
            )
        )

    if "client_id" in params:
        query = query.filter(ItemState.client_id == params.get("client_id"))

    if "name" in params:
        name = params.get("name").strip()
        query = query.filter(ItemState.name.ilike(f"{name}%"))

    if "color" in params:
        color = params.get("color").strip()
        query = query.filter(ItemState.color.ilike(f"{color}%"))

    if "default" in params:
        query = query.filter(ItemState.default == params.get("default"))

    if "is_system" in params:
        query = query.filter(ItemState.is_system == params.get("is_system"))

    sort = params.get("sort", "id_desc")
    if sort == "id_asc":
        query = query.order_by(ItemState.id.asc())
    else:
        query = query.order_by(ItemState.id.desc())

    query = apply_pagination_by_id(
        query,
        id_column=ItemState.id,
        params=params,
        sort=sort,
    )

    return query
