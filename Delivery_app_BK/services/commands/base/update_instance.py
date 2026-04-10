from flask_sqlalchemy.model import Model

from ...context import ServiceContext
from ...queries.get_instance import get_instance
from ..utils.inject_fields import inject_fields

def update_instance(
        ctx: ServiceContext,
        Model: Model,
        fields: dict,
        target_id: int | str
):
    
    instance = get_instance(
        ctx = ctx,
        model = Model,
        value = target_id,
    )

    inject_fields( 
        ctx,
        instance,
        fields,
    )

    return instance