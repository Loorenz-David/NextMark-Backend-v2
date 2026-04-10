from typing import Dict, Any
from sqlalchemy.orm import Query

from Delivery_app_BK.models import db, UserRole
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team

from ...context import ServiceContext
from ..utils import apply_pagination_by_id


def find_user_roles(
    params: Dict[str, Any],
    ctx: ServiceContext,
    query: Query | None = None,
):
    query = query or db.session.query(UserRole)

    if model_requires_team(UserRole) and ctx.inject_team_id:
        params = inject_team_id(params, ctx)

    if "team_id" in params:
        query = query.filter(UserRole.team_id == params.get("team_id"))

    if "client_id" in params:
        query = query.filter(UserRole.client_id == params.get("client_id"))

    if "role_name" in params:
        role_name = params.get("role_name").strip()
        query = query.filter(UserRole.role_name.ilike(f"{role_name}%"))

    if "base_role_id" in params:
        query = query.filter(UserRole.base_role_id == params.get("base_role_id"))

    if "is_system" in params:
        query = query.filter(UserRole.is_system == params.get("is_system"))

    sort = params.get("sort", "id_desc")
    if sort == "id_asc":
        query = query.order_by(UserRole.id.asc())
    else:
        query = query.order_by(UserRole.id.desc())

    query = apply_pagination_by_id(
        query,
        id_column=UserRole.id,
        params=params,
        sort=sort,
    )

    return query
