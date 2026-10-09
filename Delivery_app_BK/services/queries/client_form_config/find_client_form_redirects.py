from typing import Any, Dict

from sqlalchemy.orm import Query

from Delivery_app_BK.models import ClientFormRedirect, db
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team
from ...context import ServiceContext


def find_client_form_redirects(
    params: Dict[str, Any],
    ctx: ServiceContext,
    query: Query | None = None,
):
    query = query or db.session.query(ClientFormRedirect)

    # Team scoping
    if model_requires_team(ClientFormRedirect) and ctx.inject_team_id:
        params = inject_team_id(params, ctx)

    if "team_id" in params:
        query = query.filter(ClientFormRedirect.team_id == params.get("team_id"))

    if "client_id" in params:
        query = query.filter(ClientFormRedirect.client_id == params.get("client_id"))

    return query.order_by(ClientFormRedirect.created_at.asc(), ClientFormRedirect.id.asc())
