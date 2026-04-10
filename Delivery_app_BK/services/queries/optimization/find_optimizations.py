from typing import Dict, Any
from sqlalchemy.orm import Query

from Delivery_app_BK.models import db, RouteSolution
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team

from ...context import ServiceContext
from ..utils import apply_pagination_by_id


def find_optimizations(
    params: Dict[str, Any],
    ctx: ServiceContext,
    query: Query | None = None,
):
    query = query or db.session.query(RouteSolution)

    if model_requires_team(RouteSolution) and ctx.inject_team_id:
        params = inject_team_id(params, ctx)

    if "team_id" in params:
        query = query.filter(RouteSolution.team_id == params.get("team_id"))

    if "client_id" in params:
        query = query.filter(RouteSolution.client_id == params.get("client_id"))

    route_group_id = params.get("route_group_id")
    if route_group_id is not None:
        query = query.filter(
            RouteSolution.route_group_id == route_group_id
        )

    if "is_selected" in params:
        query = query.filter(
            RouteSolution.is_selected == params.get("is_selected")
        )

    if "algorithm" in params:
        algorithm = params.get("algorithm").strip()
        query = query.filter(RouteSolution.algorithm.ilike(f"{algorithm}%"))

    sort = params.get("sort", "id_desc")
    if sort == "id_asc":
        query = query.order_by(RouteSolution.id.asc())
    else:
        query = query.order_by(RouteSolution.id.desc())

    query = apply_pagination_by_id(
        query,
        id_column=RouteSolution.id,
        params=params,
        sort=sort,
    )

    return query
