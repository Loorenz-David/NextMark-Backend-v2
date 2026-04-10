from typing import Dict, Any
from sqlalchemy.orm import Query

from Delivery_app_BK.models import db, TeamInvites

from ....context import ServiceContext
from ...utils import apply_pagination_by_id


def find_team_invites_received(
    params: Dict[str, Any],
    ctx: ServiceContext,
    query: Query | None = None,
):
    query = query or db.session.query(TeamInvites)

    if ctx.user_id:
        params = dict(params)
        params["target_user_id"] = ctx.user_id

    if "client_id" in params:
        query = query.filter(TeamInvites.client_id == params.get("client_id"))

    if "user_id" in params:
        query = query.filter(TeamInvites.target_user_id == params.get("user_id"))

    if "target_user_id" in params:
        query = query.filter(TeamInvites.target_user_id == params.get("target_user_id"))

    if "from_team_name" in params:
        team_name = params.get("from_team_name").strip()
        query = query.filter(TeamInvites.from_team_name.ilike(f"{team_name}%"))

    if "role_id" in params:
        query = query.filter(TeamInvites.user_role_id == params.get("role_id"))

    if "user_role_id" in params:
        query = query.filter(TeamInvites.user_role_id == params.get("user_role_id"))

    if "user_role_name" in params:
        role_name = params.get("user_role_name").strip()
        query = query.filter(TeamInvites.user_role_name.ilike(f"{role_name}%"))

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
