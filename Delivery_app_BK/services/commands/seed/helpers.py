from typing import Any, Tuple, Type

from flask_sqlalchemy.model import Model

from Delivery_app_BK.models import db
from Delivery_app_BK.services.commands.utils.client_id_generator import generate_client_id

from ..base.create_instance import create_instance
from ...context import ServiceContext


def get_or_create(
    ctx: ServiceContext,
    model: Type[Model],
    lookup: dict,
    defaults: dict | None = None,
) -> Tuple[Model, bool]:

    instance = db.session.query(model).filter_by(**lookup).first()
   
    if instance:
        return instance, False

    fields = dict(lookup)
    if defaults:
        fields.update(defaults)
    instance = create_instance(ctx, model, fields)
    db.session.add(instance)
    return instance, True


def ensure_client_id(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("client_id"):
        payload["client_id"] = generate_client_id()
    return payload
