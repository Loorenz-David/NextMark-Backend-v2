from typing import Dict, Any
from sqlalchemy.orm import Query

from Delivery_app_BK.models import db, Item
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team

from ...context import ServiceContext
from ..utils import apply_pagination_by_id


def find_items(
        params: Dict[str, Any],
        ctx: ServiceContext,
        query: Query | None = None,
):
    query = query or db.session.query(Item)
    trimmed_query = str(params.get("q")).strip()

    if model_requires_team( Item ) and ctx.inject_team_id:
        params = inject_team_id( params, ctx )
    
    if "team_id" in params:
        query = query.filter( Item.team_id == params.get( "team_id" ) )

    if "client_id" in params:
        query = query.filter(Item.client_id == params.get("client_id"))

    if "article_number" in params:
        query = query.filter(Item.article_number.ilike(f"{trimmed_query}%"))

    if "item_type" in params:

        query = query.filter(Item.item_type.ilike(f"{trimmed_query}%"))

    if "item_state_id" in params:
        state_ids = params.get("item_state_id")
        if not isinstance(state_ids, (list, tuple)):
            state_ids = [state_ids]
        query = query.filter(Item.item_state_id.in_(state_ids))

    if "item_position_id" in params:
        position_ids = params.get("item_position_id")
        if not isinstance(position_ids, (list, tuple)):
            position_ids = [position_ids]
        query = query.filter(Item.item_position_id.in_(position_ids))

    if "order_id" in params:
        order_ids = params.get("order_id")
        if not isinstance(order_ids, (list, tuple)):
            order_ids = [order_ids]
        query = query.filter(Item.order_id.in_(order_ids))

    if "weight_min" in params:
        query = query.filter(Item.weight >= params.get("weight_min"))

    if "weight_max" in params:
        query = query.filter(Item.weight <= params.get("weight_max"))

    if "item_type_exact" in params:
        query = query.filter(Item.item_type == params.get("item_type_exact"))

    if "quantity_min" in params:
        query = query.filter(Item.quantity >= int(params.get("quantity_min")))

    if "quantity_max" in params:
        query = query.filter(Item.quantity <= int(params.get("quantity_max")))

    if "is_system" in params:
        query = query.filter(Item.is_system.is_(bool(params.get("is_system"))))

    if "dimension_volume_min_cm3" in params:
        vol = Item.dimension_depth * Item.dimension_height * Item.dimension_width
        query = query.filter(vol >= float(params.get("dimension_volume_min_cm3")))

    if "dimension_volume_max_cm3" in params:
        vol = Item.dimension_depth * Item.dimension_height * Item.dimension_width
        query = query.filter(vol <= float(params.get("dimension_volume_max_cm3")))


    sort = params.get("sort", "id_desc")
    if sort == "id_asc":
        query = query.order_by(Item.id.asc())
    else:
        query = query.order_by(Item.id.desc())

    #---------------------------------------
    

     # pagination -------------------------
    query = apply_pagination_by_id(
        query,
        id_column=Item.id,
        params=params,
        sort=sort,
    )
    #---------------------------------------

    return query
