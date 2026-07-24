from ...context import ServiceContext
from .find_client_form_rules import find_client_form_rules
from .serialize_client_form_config import serialize_client_form_rules


def list_client_form_rules(ctx: ServiceContext):
    instances = find_client_form_rules(ctx.query_params, ctx).all()

    return {"client_form_rules": serialize_client_form_rules(instances, ctx)}
