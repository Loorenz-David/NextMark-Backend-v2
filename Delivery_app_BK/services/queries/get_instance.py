from flask_sqlalchemy.model import Model
from typing import Type 

from ..context import ServiceContext

from Delivery_app_BK.services.utils import ensure_instance_in_team, model_requires_team, is_system_default
from sqlalchemy.orm.exc import NoResultFound
from Delivery_app_BK.models import db

def get_instance(
        ctx:ServiceContext,
        model: Model, 
        value: Type[ Model ] | int, 
) -> Type[ Model ]:
    if isinstance(value, model):
        obj = value
    else:
        # uses db id to get the object
        if isinstance( value, int):
            obj = db.session.get(model, value)

        if isinstance( value, str ):
            obj = db.session.query( Model ).filter_by( client_id = value ).one()

        if not obj:
            raise NoResultFound(
                f"No {model.__name__} found with id '{value}'"
            )

    if model_requires_team(model) and ctx.check_team_id:
        if not is_system_default(obj):
            ensure_instance_in_team(obj, ctx)

    return obj