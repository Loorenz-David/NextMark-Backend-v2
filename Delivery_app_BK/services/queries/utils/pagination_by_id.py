from typing import Dict, Any
from sqlalchemy.orm import Query
from sqlalchemy.orm.attributes import InstrumentedAttribute

from ...context import ServiceContext


def apply_pagination_by_id(
        query: Query,
        *,
        id_column: InstrumentedAttribute,
        params: Dict[str, Any],
        sort: str = "id_desc",
):
    after_id = params.get("after_id")
    before_id = params.get("before_id")

    if after_id:
        after_id = int(after_id)
        if sort == "id_asc":
            query = query.filter(id_column > after_id)
        else:
            query = query.filter(id_column < after_id)
    elif before_id:
        before_id = int(before_id)
        if sort == "id_asc":
            query = query.filter(id_column < before_id)
        else:
            query = query.filter(id_column > before_id)

    return query


def build_id_pagination(
        page_instances: list,
        *,
        has_more: bool,
        ctx: ServiceContext,
        id_attr: str = "id",
):
    if not page_instances:
        return {"has_more": False, "next_cursor": None, "prev_cursor": None}

    if "before_id" in ctx.query_params:
        page_instances.reverse()

    return {
        "has_more": has_more,
        "next_cursor": {"after_id": getattr(page_instances[-1], id_attr)},
        "prev_cursor": {"before_id": getattr(page_instances[0], id_attr)},
    }
