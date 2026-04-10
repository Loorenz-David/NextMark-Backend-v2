from typing import Dict, Any
from sqlalchemy.orm import Query

from Delivery_app_BK.models import db, TeamInvites
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team

from ....context import ServiceContext
from ...utils import apply_pagination_by_id


def find_team_invites_sent(
    params: Dict[str, Any],
    ctx: ServiceContext,
    query: Query | None = None,
):
    query = query or db.session.query(TeamInvites)

    if model_requires_team(TeamInvites) and ctx.inject_team_id:
        params = inject_team_id(params, ctx)

    if "team_id" in params:
        query = query.filter(TeamInvites.team_id == params.get("team_id"))

    if "client_id" in params:
        query = query.filter(TeamInvites.client_id == params.get("client_id"))

    if "user_id" in params:
        query = query.filter(TeamInvites.target_user_id == params.get("user_id"))

    if "target_user_id" in params:
        query = query.filter(TeamInvites.target_user_id == params.get("target_user_id"))

    if "username" in params:
        username = params.get("username").strip()
        query = query.filter(TeamInvites.target_username.ilike(f"{username}%"))

    if "target_username" in params:
        username = params.get("target_username").strip()
        query = query.filter(TeamInvites.target_username.ilike(f"{username}%"))

    if "email" in params:
        email = params.get("email").strip()
        query = query.filter(TeamInvites.target_email.ilike(f"{email}%"))

    if "target_email" in params:
        email = params.get("target_email").strip()
        query = query.filter(TeamInvites.target_email.ilike(f"{email}%"))

    if "role_id" in params:
        query = query.filter(TeamInvites.user_role_id == params.get("role_id"))

    if "user_role_id" in params:
        query = query.filter(TeamInvites.user_role_id == params.get("user_role_id"))

    sort = params.get("sort", "id_desc")
    if sort == "id_asc":
        query = query.order_by(TeamInvites.id.asc())
    else:
        query = query.order_by(TeamInvites.id.desc())

    query = apply_pagination_by_id(
        query,
        id_column=TeamInvites.id,
        params=params,
        sort=sort,
    )

    return query
