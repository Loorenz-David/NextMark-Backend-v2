from typing import Dict, Any
from sqlalchemy.orm import Query
from sqlalchemy import or_

from Delivery_app_BK.models import db, User
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team

from ...context import ServiceContext
from ..utils import apply_pagination_by_id


def find_team_members(
    params: Dict[str, Any],
    ctx: ServiceContext,
    query: Query | None = None,
):
    query = query or db.session.query(User)

    if model_requires_team(User) and ctx.inject_team_id:
        params = inject_team_id(params, ctx)

    if "team_id" in params:
        team_id = params.get("team_id")
        query = query.filter(
            or_(
                User.team_id == team_id,
                User.team_workspace_team_id == team_id,
            )
        )

    if "client_id" in params:
        query = query.filter(User.client_id == params.get("client_id"))

    if "username" in params:
        username = params.get("username").strip()
        query = query.filter(User.username.ilike(f"{username}%"))

    if "email" in params:
        email = params.get("email").strip()
        query = query.filter(User.email.ilike(f"{email}%"))

    if "role_id" in params:
        query = query.filter(User.role_id == params.get("role_id"))

    sort = params.get("sort", "id_desc")
    if sort == "id_asc":
        query = query.order_by(User.id.asc())
    else:
        query = query.order_by(User.id.desc())

    query = apply_pagination_by_id(
        query,
        id_column=User.id,
        params=params,
        sort=sort,
    )

    return query
