from typing import Dict, Any
from sqlalchemy.orm import Query

from Delivery_app_BK.models import db, ItemPosition
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team

from ...context import ServiceContext
from ..utils import apply_pagination_by_id


def find_item_positions(
    params: Dict[str, Any],
    ctx: ServiceContext,
    query: Query | None = None,
):
    query = query or db.session.query(ItemPosition)

    if model_requires_team(ItemPosition) and ctx.inject_team_id:
        params = inject_team_id(params, ctx)

    if "team_id" in params:
        query = query.filter(ItemPosition.team_id == params.get("team_id"))

    if "client_id" in params:
        query = query.filter(ItemPosition.client_id == params.get("client_id"))

    if "name" in params:
        name = params.get("name").strip()
        query = query.filter(ItemPosition.name.ilike(f"{name}%"))

    if "default" in params:
        query = query.filter(ItemPosition.default == params.get("default"))

    sort = params.get("sort", "id_desc")
    if sort == "id_asc":
        query = query.order_by(ItemPosition.id.asc())
    else:
        query = query.order_by(ItemPosition.id.desc())

    query = apply_pagination_by_id(
        query,
        id_column=ItemPosition.id,
        params=params,
        sort=sort,
    )

    return query
