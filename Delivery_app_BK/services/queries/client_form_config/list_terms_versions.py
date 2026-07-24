from ...context import ServiceContext
from .find_terms_versions import find_terms_versions
from .serialize_client_form_config import serialize_terms_versions


def list_terms_versions(ctx: ServiceContext):
    """Return the team's terms history, newest version first."""
    instances = find_terms_versions(ctx.query_params, ctx).all()

    return {"client_form_terms_versions": serialize_terms_versions(instances, ctx)}
