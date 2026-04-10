from typing import Dict, Any
from sqlalchemy.orm import Query

from Delivery_app_BK.models import db, LabelTemplate
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team

from ....context import ServiceContext
from ...utils import apply_pagination_by_id


def find_label_templates(
    params: Dict[str, Any],
    ctx: ServiceContext,
    query: Query | None = None,
):
    query = query or db.session.query(LabelTemplate)

    if model_requires_team(LabelTemplate) and ctx.inject_team_id:
        params = inject_team_id(params, ctx)

    if "team_id" in params:
        query = query.filter(LabelTemplate.team_id == params.get("team_id"))

    if "client_id" in params:
        query = query.filter(LabelTemplate.client_id == params.get("client_id"))

    if "name" in params:
        name = params.get("name").strip()
        query = query.filter(LabelTemplate.name.ilike(f"{name}%"))

    if "template_target" in params:
        query = query.filter(
            LabelTemplate.template_target == params.get("template_target")
        )

    if "is_system" in params:
        query = query.filter(LabelTemplate.is_system == params.get("is_system"))

    sort = params.get("sort", "id_desc")
    if sort == "id_asc":
        query = query.order_by(LabelTemplate.id.asc())
    else:
        query = query.order_by(LabelTemplate.id.desc())

    query = apply_pagination_by_id(
        query,
        id_column=LabelTemplate.id,
        params=params,
        sort=sort,
    )

    return query
