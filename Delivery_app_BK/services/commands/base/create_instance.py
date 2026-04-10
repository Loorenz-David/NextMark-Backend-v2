
from flask_sqlalchemy.model import Model
from typing import Type

from Delivery_app_BK.errors import ValidationFailed

from ...context import ServiceContext
from ...utils import model_requires_team, inject_team_id
from ..utils.inject_fields import inject_fields
from ..utils import generate_client_id



def create_instance( 
        ctx: ServiceContext,
        Model: Model,
        fields: dict,
) -> Type[ Model ]:
    if Model is None:
        raise ValidationFailed("Model is required to create an instance.")
    if fields is None:
        raise ValidationFailed("Fields are required to create an instance.")


    if ctx.inject_team_id:
        if model_requires_team( Model ):
            fields = inject_team_id( fields, ctx )

    fields = _ensure_client_id(Model, fields)

    new_instance = Model()

    inject_fields( 
        ctx,
        new_instance,
        fields
    )
    
    return new_instance


def _ensure_client_id(model: Model, fields: dict) -> dict:
    table = getattr(model, "__table__", None)
    if table is None or "client_id" not in table.columns:
        return fields

    client_id = fields.get("client_id")
    if isinstance(client_id, str) and client_id.strip():
        return fields

    resolved_fields = dict(fields)
    prefix = getattr(model, "__tablename__", None) or model.__name__.lower()
    resolved_fields["client_id"] = generate_client_id(prefix)
    return resolved_fields
