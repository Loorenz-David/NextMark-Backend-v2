from typing import List, Type
from flask_sqlalchemy.model import Model

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db

from ...context import ServiceContext
from ...utils import ensure_instance_in_team
from ...queries.get_instance import get_instance



def delete_instance( 
        ctx: ServiceContext,
        Model: Model,
        target: int | str | Type[ Model ]
):
    if Model is None:
        raise ValidationFailed("Model is required to create an instance.")
    if target is None:
        raise ValidationFailed("Target ids are required to remove an instance.")
    

    target_instance = get_instance(
        ctx = ctx,
        model = Model, 
        value = target, 
    )

    db.session.delete( target_instance )

    return target_instance