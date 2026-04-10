
from Delivery_app_BK.models import db, Costumer
from Delivery_app_BK.errors import NotFound
from sqlalchemy.orm import selectinload


from ...context import ServiceContext
from .serialize_costumer import serialize_costumers


def get_costumer( costumer_id: int, ctx:ServiceContext ):
    query = db.session.query(Costumer).options(
        selectinload(Costumer.operating_hours),
        selectinload(Costumer.orders),
    )
    if ctx.team_id:
        query = query.filter(Costumer.team_id == ctx.team_id)
    found_costumer = query.filter(Costumer.id == costumer_id).first()

    if not found_costumer:
        raise NotFound(f"costumer with id: {costumer_id} does not exist.")    
    
    serialize_object = serialize_costumers(
        instances = [ found_costumer ],
        include_order_count=True,
    )

    return {
        "costumer": serialize_object[0] if isinstance( serialize_object, list ) else serialize_object
    }
