from typing import Dict

from Delivery_app_BK.models import BaseRole
from Delivery_app_BK.services.context import ServiceContext

from ..data import BASE_ROLE_SEEDS
from ..helpers import ensure_client_id, get_or_create


def seed_base_roles(ctx: ServiceContext) -> Dict[str, BaseRole]:
    base_roles: Dict[str, BaseRole] = {}

    for payload in BASE_ROLE_SEEDS:
        fields = ensure_client_id(dict(payload))
        lookup = {"role_name": fields["role_name"]}
        instance, _ = get_or_create(ctx, BaseRole, lookup, fields)
        base_roles[fields["role_name"]] = instance

    return base_roles
