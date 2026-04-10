from typing import Type
from flask_sqlalchemy.model import Model

from ...context import ServiceContext
from ..utils import map_return_values


def serialize_date_range_access_rules(instances: Type[Model], ctx: ServiceContext):
    unpacked_instances = []

    for instance in instances:
        from_date = instance.from_date
        to_date = instance.to_date
        unpacked = {
            "id": instance.id,
            "client_id": instance.client_id,
            "from_date": from_date.isoformat() if from_date else None,
            "to_date": to_date.isoformat() if to_date else None,
            "target_model": instance.target_model,
            "user_role_id": instance.user_role_id,

        }
        unpacked_instances.append(unpacked)

    return map_return_values(unpacked_instances, ctx, "date_range_access_rule")
