from typing import Dict, Any
from sqlalchemy import false
from sqlalchemy.orm import Query

from Delivery_app_BK.models import db, MessageTemplate
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team
from Delivery_app_BK.services.queries.utils import parsed_string_to_list
from ....context import ServiceContext
from ...utils import apply_pagination_by_id


def find_message_templates(
    params: Dict[str, Any],
    ctx: ServiceContext,
    query: Query | None = None,
):
    query = query or db.session.query(MessageTemplate)

    # Team scoping
    if model_requires_team(MessageTemplate) and ctx.inject_team_id:
        params = inject_team_id(params, ctx)

    if "team_id" in params:
        query = query.filter(MessageTemplate.team_id == params.get("team_id"))

    # Model-aligned filters
    if "client_id" in params:
        query = query.filter(MessageTemplate.client_id == params.get("client_id"))

    if "name" in params:
        name = params.get("name").strip()
        query = query.filter(MessageTemplate.name.ilike(f"{name}%"))

    if "channel" in params:
        channel = params.get("channel").strip()
        query = query.filter(MessageTemplate.channel == channel)

    if "event" in params:
        query = query.filter(MessageTemplate.event == params.get("event"))

    if "enable" in params:
        query = query.filter(MessageTemplate.enable == params.get("enable"))

    plan_type_filter_values = _resolve_plan_type_filter_values(params, ctx)
    if plan_type_filter_values:
        normalized_plan_types = []
        for value in plan_type_filter_values:
            stripped = str(value).strip()
            if stripped:
                normalized_plan_types.append(stripped)

        deduped_plan_types = list(dict.fromkeys(normalized_plan_types))
        if deduped_plan_types:
            query = query.filter(MessageTemplate.plan_type.in_(deduped_plan_types))
        else:
            query = query.filter(false())

    # Sorting
    sort = params.get("sort", "id_desc")
    if sort == "id_asc":
        query = query.order_by(MessageTemplate.id.asc())
    else:
        query = query.order_by(MessageTemplate.id.desc())

    # Pagination
    query = apply_pagination_by_id(
        query,
        id_column=MessageTemplate.id,
        params=params,
        sort=sort,
    )

    return query


def _resolve_plan_type_filter_values(params: Dict[str, Any], ctx: ServiceContext) -> list[Any]:
    query_params = getattr(ctx, "query_params", None)
    if query_params is not None and hasattr(query_params, "getlist"):
        values = query_params.getlist("plan_type[]")
        if values:
            return values

        values = query_params.getlist("plan_type")
        if values:
            return values

    if "plan_type[]" in params:
        values = params.get("plan_type[]")
        if isinstance(values, (list, tuple)):
            return list(values)
        return [values]

    if "plan_type" not in params:
        return []

    values = params.get("plan_type")
    if isinstance(values, (list, tuple)):
        return list(values)

    parsed_values = parsed_string_to_list(values, ctx)
    if isinstance(parsed_values, list):
        return parsed_values

    return [values]
