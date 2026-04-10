from ....context import ServiceContext
from ...utils import build_id_pagination
from .find_message_templates import find_message_templates
from .serialize_message_templates import serialize_message_templates, serialize_message_templates_bootstrap


def list_message_templates(ctx: ServiceContext):
    query = find_message_templates(ctx.query_params, ctx)

    limit = int(ctx.query_params.get("limit", 50))
    results = query.limit(limit + 1).all()
    has_more = len(results) > limit
    page_instances = results[:limit]

    pagination = build_id_pagination(
        page_instances=page_instances,
        has_more=has_more,
        ctx=ctx,
    )

    serialized = serialize_message_templates(
        instances=page_instances,
        ctx=ctx,
    )

    return {
        "message_templates": serialized,
        "message_templates_pagination": pagination,
    }

def list_message_templates_bootstrap(ctx: ServiceContext):
    query = find_message_templates(ctx.query_params, ctx)

    limit = int(ctx.query_params.get("limit", 50))
    results = query.limit(limit + 1).all()
    has_more = len(results) > limit
    page_instances = results[:limit]

    pagination = build_id_pagination(
        page_instances=page_instances,
        has_more=has_more,
        ctx=ctx,
    )

    serialized = serialize_message_templates_bootstrap(
        instances=page_instances,
        ctx=ctx,
    )

    return {
        "message_templates": serialized,
        "message_templates_pagination": pagination,
    }
