from ....context import ServiceContext
from ...utils import build_id_pagination
from .find_label_templates import find_label_templates
from .serialize_label_templates import serialize_label_templates, serialize_label_templates_bootstrap


def list_label_templates(ctx: ServiceContext):
    query = find_label_templates(ctx.query_params, ctx)

    limit = int(ctx.query_params.get("limit", 10))
    results = query.limit(limit + 1).all()
    page_instances = results[:limit]


    serialized = serialize_label_templates(
        instances=page_instances,
        ctx=ctx,
    )

    return {
        "label_templates": serialized,
    }

def list_label_templates_bootstrap(ctx:ServiceContext):
    query = find_label_templates(ctx.query_params, ctx)

    limit = int(ctx.query_params.get("limit", 10))
    results = query.limit(limit + 1).all()
    page_instances = results[:limit]

    serialized = serialize_label_templates_bootstrap(
        instances=page_instances,
        ctx=ctx,
    )

    return {
        "label_templates": serialized,
    }
