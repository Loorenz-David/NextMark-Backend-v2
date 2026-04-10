from Delivery_app_BK.models import db, Item

from ...context import ServiceContext
from ..utils import build_id_pagination
from .find_items import find_items
from .serialize_items import serialize_items


def list_items(ctx: ServiceContext, order_id: int | None = None):
    base_query = db.session.query(Item)
    if order_id is not None:
        base_query = base_query.filter(Item.order_id == order_id)

    query = find_items(ctx.query_params, ctx, query=base_query)

    limit = int(ctx.query_params.get("limit", 50))
    results = query.limit(limit + 1).all()
    has_more = len(results) > limit

    page_instances = results[:limit]

    pagination = build_id_pagination(
        page_instances=page_instances,
        has_more=has_more,
        ctx=ctx,
    )

    serialized_objects = serialize_items(
        instances=page_instances,
        ctx=ctx,
    )

    return {
        "items": serialized_objects,
        "items_pagination": pagination,
    }
