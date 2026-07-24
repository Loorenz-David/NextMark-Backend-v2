from typing import Any, Dict

from sqlalchemy.orm import Query

from Delivery_app_BK.models import ClientFormRule, db
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team
from ...context import ServiceContext
from ..utils import str_to_bool


def find_client_form_rules(
    params: Dict[str, Any],
    ctx: ServiceContext,
    query: Query | None = None,
):
    query = query or db.session.query(ClientFormRule)

    # Team scoping
    if model_requires_team(ClientFormRule) and ctx.inject_team_id:
        params = inject_team_id(params, ctx)

    if "team_id" in params:
        query = query.filter(ClientFormRule.team_id == params.get("team_id"))

    if "client_id" in params:
        query = query.filter(ClientFormRule.client_id == params.get("client_id"))

    if "enabled" in params:
        query = query.filter(ClientFormRule.enabled.is_(str_to_bool(params.get("enabled"))))

    return query.order_by(ClientFormRule.position.asc(), ClientFormRule.id.asc())
