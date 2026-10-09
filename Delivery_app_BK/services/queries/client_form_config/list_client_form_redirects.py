from ...context import ServiceContext
from .find_client_form_redirects import find_client_form_redirects
from .serialize_client_form_config import serialize_client_form_redirects


def list_client_form_redirects(ctx: ServiceContext):
    instances = find_client_form_redirects(ctx.query_params, ctx).all()

    return {"client_form_redirects": serialize_client_form_redirects(instances, ctx)}
