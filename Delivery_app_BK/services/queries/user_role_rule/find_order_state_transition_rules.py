from typing import Dict, Any
from sqlalchemy.orm import Query

from Delivery_app_BK.models import db, OrderStateTransitionRule
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team

from ...context import ServiceContext
from ..utils import apply_pagination_by_id


def find_order_state_transition_rules(
    params: Dict[str, Any],
    ctx: ServiceContext,
    query: Query | None = None,
):
    query = query or db.session.query(OrderStateTransitionRule)

    if model_requires_team(OrderStateTransitionRule) and ctx.inject_team_id:
        params = inject_team_id(params, ctx)

    if "team_id" in params:
        query = query.filter(OrderStateTransitionRule.team_id == params.get("team_id"))

    if "client_id" in params:
        query = query.filter(OrderStateTransitionRule.client_id == params.get("client_id"))

    if "user_role_id" in params:
        query = query.filter(
            OrderStateTransitionRule.user_role_id == params.get("user_role_id")
        )

    if "allowed_state_id" in params:
        query = query.filter(
            OrderStateTransitionRule.allowed_state_id == params.get("allowed_state_id")
        )

    sort = params.get("sort", "id_desc")
    if sort == "id_asc":
        query = query.order_by(OrderStateTransitionRule.id.asc())
    else:
        query = query.order_by(OrderStateTransitionRule.id.desc())

    query = apply_pagination_by_id(
        query,
        id_column=OrderStateTransitionRule.id,
        params=params,
        sort=sort,
    )

    return query
