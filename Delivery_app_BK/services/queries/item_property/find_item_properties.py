from typing import Dict, Any
from sqlalchemy.orm import Query

from Delivery_app_BK.models import db, ItemProperty
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team

from ...context import ServiceContext
from ..utils import apply_pagination_by_id


def find_item_properties(
    params: Dict[str, Any],
    ctx: ServiceContext,
    query: Query | None = None,
):
    query = query or db.session.query(ItemProperty)

    if model_requires_team(ItemProperty) and ctx.inject_team_id:
        params = inject_team_id(params, ctx)

    if "team_id" in params:
        query = query.filter(ItemProperty.team_id == params.get("team_id"))

    if "client_id" in params:
        query = query.filter(ItemProperty.client_id == params.get("client_id"))

    if "name" in params:
        name = params.get("name").strip()
        query = query.filter(ItemProperty.name.ilike(f"{name}%"))

    if "field_type" in params:
        field_type = params.get("field_type").strip()
        query = query.filter(ItemProperty.field_type.ilike(f"{field_type}%"))

    if "required" in params:
        query = query.filter(ItemProperty.required == params.get("required"))

    sort = params.get("sort", "id_desc")
    if sort == "id_asc":
        query = query.order_by(ItemProperty.id.asc())
    else:
        query = query.order_by(ItemProperty.id.desc())

    query = apply_pagination_by_id(
        query,
        id_column=ItemProperty.id,
        params=params,
        sort=sort,
    )

    return query
