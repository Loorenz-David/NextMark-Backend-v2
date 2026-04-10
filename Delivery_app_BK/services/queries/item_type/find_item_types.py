from typing import Dict, Any
from sqlalchemy.orm import Query

from Delivery_app_BK.models import db, ItemType
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team

from ...context import ServiceContext
from ..utils import apply_pagination_by_id


def find_item_types(
    params: Dict[str, Any],
    ctx: ServiceContext,
    query: Query | None = None,
):
    query = query or db.session.query(ItemType)

    if model_requires_team(ItemType) and ctx.inject_team_id:
        params = inject_team_id(params, ctx)

    if "team_id" in params:
        query = query.filter(ItemType.team_id == params.get("team_id"))

    if "client_id" in params:
        query = query.filter(ItemType.client_id == params.get("client_id"))

    if "name" in params:
        name = params.get("name").strip()
        query = query.filter(ItemType.name.ilike(f"{name}%"))

    if "item_category_id" in params:
        query = query.filter(ItemType.item_category_id == params.get("item_category_id"))

    sort = params.get("sort", "id_desc")
    if sort == "id_asc":
        query = query.order_by(ItemType.id.asc())
    else:
        query = query.order_by(ItemType.id.desc())

    query = apply_pagination_by_id(
        query,
        id_column=ItemType.id,
        params=params,
        sort=sort,
    )

    return query
