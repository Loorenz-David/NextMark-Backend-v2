from ...context import ServiceContext
from .find_client_form_media import find_client_form_media
from .serialize_client_form_config import serialize_client_form_media


def list_client_form_media(ctx: ServiceContext):
    instances = find_client_form_media(ctx.query_params, ctx).all()

    return {"client_form_media": serialize_client_form_media(instances, ctx)}
