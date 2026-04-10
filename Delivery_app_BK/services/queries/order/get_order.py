
from Delivery_app_BK.models import db, Order
from Delivery_app_BK.errors import NotFound
from sqlalchemy.orm import selectinload


from ...context import ServiceContext
from .serialize_order import serialize_orders


def get_order( order_id: int, ctx:ServiceContext ):
    query = db.session.query(Order).options(selectinload(Order.delivery_windows))
    if ctx.team_id:
        query = query.filter(Order.team_id == ctx.team_id)
    found_order = query.filter(Order.id == order_id).first()

    if not found_order:
        raise NotFound(f"Order with id: {order_id} does not exist.")    
    
    serialize_object = serialize_orders(
        instances = [ found_order ],
        ctx = ctx
    )

    return {
        "order": serialize_object[0] if isinstance( serialize_object, list ) else serialize_object
    }
