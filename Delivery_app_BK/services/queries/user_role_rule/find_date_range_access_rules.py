from typing import Dict, Any
from sqlalchemy.orm import Query

from Delivery_app_BK.models import db, DateRangeAccessRule
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team

from ...context import ServiceContext
from ..utils import apply_pagination_by_id


def find_date_range_access_rules(
    params: Dict[str, Any],
    ctx: ServiceContext,
    query: Query | None = None,
):
    query = query or db.session.query(DateRangeAccessRule)

    if model_requires_team(DateRangeAccessRule) and ctx.inject_team_id:
        params = inject_team_id(params, ctx)

    if "team_id" in params:
        query = query.filter(DateRangeAccessRule.team_id == params.get("team_id"))

    if "client_id" in params:
        query = query.filter(DateRangeAccessRule.client_id == params.get("client_id"))

    if "user_role_id" in params:
        query = query.filter(DateRangeAccessRule.user_role_id == params.get("user_role_id"))

    if "target_model" in params:
        target_model = params.get("target_model").strip()
        query = query.filter(DateRangeAccessRule.target_model.ilike(f"{target_model}%"))

    sort = params.get("sort", "id_desc")
    if sort == "id_asc":
        query = query.order_by(DateRangeAccessRule.id.asc())
    else:
        query = query.order_by(DateRangeAccessRule.id.desc())

    query = apply_pagination_by_id(
        query,
        id_column=DateRangeAccessRule.id,
        params=params,
        sort=sort,
    )

    return query
