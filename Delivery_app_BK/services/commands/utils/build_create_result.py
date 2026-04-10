from typing import Type, List
from flask_sqlalchemy.model import Model

from Delivery_app_BK.errors import ValidationFailed

from ...context import ServiceContext
from . import build_dynamic_ids_map


def build_create_result(
        ctx: ServiceContext,
        instances: List[Type[Model]],
        extract_fields: list | None = None,
):
    if ctx is None:
        raise ValidationFailed("Service context is required to build create results.")
    if not isinstance(instances, list):
        raise ValidationFailed("Instances must be provided as a list.")

    mode = ctx.on_create_return

    if mode == "instances":
        return instances

    elif mode == "map_ids_object":
        return build_dynamic_ids_map(
            instances,
            extract_fields=extract_fields,
            ctx=ctx,
        )

    elif mode == "ids":
        ids = []
        for instance in instances:
            if not hasattr(instance, "id"):
                raise ValidationFailed("Instance is missing an 'id' attribute.")
            ids.append(instance.id)
        return ids

    raise ValidationFailed(f"Unknown on_create_return mode: {mode}")
