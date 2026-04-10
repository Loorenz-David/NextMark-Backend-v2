from typing import Dict, Any
from sqlalchemy.orm import Query
from sqlalchemy import or_

from Delivery_app_BK.models import db, RoutePlanState
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team

from ...utils import apply_pagination_by_id


def find_plan_states(
    params: Dict[str, Any],
    ctx: ServiceContext,
    query: Query | None = None,
):
    query = query or db.session.query(RoutePlanState)

    if model_requires_team(RoutePlanState) and ctx.inject_team_id:
        params = inject_team_id(params, ctx)

    if "team_id" in params:
         query = query.filter(
            or_(
                RoutePlanState.is_system.is_(True),
                RoutePlanState.team_id == params["team_id"],
            )
        )

    if "client_id" in params:
        query = query.filter(RoutePlanState.client_id == params.get("client_id"))

    if "name" in params:
        name = params.get("name").strip()
        query = query.filter(RoutePlanState.name.ilike(f"{name}%"))

    if "color" in params:
        color = params.get("color").strip()
        query = query.filter(RoutePlanState.color.ilike(f"{color}%"))

    if "index" in params:
        query = query.filter(RoutePlanState.index == params.get("index"))

    if "is_system" in params:
        query = query.filter(RoutePlanState.is_system == params.get("is_system"))

    sort = params.get("sort", "id_desc")
    if sort == "id_asc":
        query = query.order_by(RoutePlanState.id.asc())
    else:
        query = query.order_by(RoutePlanState.id.desc())

    query = apply_pagination_by_id(
        query,
        id_column=RoutePlanState.id,
        params=params,
        sort=sort,
    )

    return query
