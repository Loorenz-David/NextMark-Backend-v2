from typing import Dict
from sqlalchemy import or_, and_

from Delivery_app_BK.models import db, RoutePlan
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team

from ...context import ServiceContext
from ...utils import to_datetime

from ..order.find_orders import find_orders
from ..utils import apply_opaque_pagination_by_date

"""
For adding a filter use:
    if "" in params:
        query = query.filter(RoutePlan.<field> == params[""])
"""

def find_plans( params:Dict, ctx:ServiceContext ):

    query = db.session.query(RoutePlan)

    if model_requires_team( RoutePlan ) and ctx.inject_team_id:
        params = inject_team_id( params, ctx )
    
    if "team_id" in params:
        query = query.filter( RoutePlan.team_id == params.get( "team_id" ) )


    if "label" in params:
        label = params.get("label", "").strip()
        query = query.filter( RoutePlan.label.ilike( f"{label}%") )

    if "date_strategy" in params:
        query = query.filter(RoutePlan.date_strategy == params["date_strategy"])

    if "start_date" in params:
        start_date = to_datetime( params[ "start_date" ] )
        query = query.filter( RoutePlan.start_date >= start_date ) 

    if "end_date" in params:
        end_date = to_datetime( params[ "end_date" ] )
        query = query.filter( RoutePlan.end_date <= end_date )

    if "created_at_from" in params:
        created_at_from = to_datetime( params[ "created_at_from" ] )
        query = query.filter( RoutePlan.created_at >= created_at_from )
        
    if "created_at_to" in params:
        created_at_to = to_datetime( params[ "created_at_to" ] )
        query = query.filter( RoutePlan.created_at <= created_at_to )

    if "state_id" in params:
        query = query.filter(RoutePlan.state_id == params["state_id"])

    # overlap filter: find plans whose window covers a target date range
    # condition: plan.start_date <= covers_end AND plan.end_date >= covers_start
    if "covers_start" in params and "covers_end" in params:
        covers_start = to_datetime( params["covers_start"] )
        covers_end   = to_datetime( params["covers_end"] )
        query = query.filter(
            RoutePlan.start_date <= covers_end,
            RoutePlan.end_date   >= covers_start,
        )

    # order count filters (uses denormalized total_orders column)
    if "max_orders" in params:
        query = query.filter( RoutePlan.total_orders <= int(params["max_orders"]) )

    if "min_orders" in params:
        query = query.filter( RoutePlan.total_orders >= int(params["min_orders"]) )

    if "total_weight_min_g" in params:
        query = query.filter(RoutePlan.total_weight_g >= float(params["total_weight_min_g"]))

    if "total_weight_max_g" in params:
        query = query.filter(RoutePlan.total_weight_g <= float(params["total_weight_max_g"]))

    if "total_volume_min_cm3" in params:
        query = query.filter(RoutePlan.total_volume_cm3 >= float(params["total_volume_min_cm3"]))

    if "total_volume_max_cm3" in params:
        query = query.filter(RoutePlan.total_volume_cm3 <= float(params["total_volume_max_cm3"]))

    if "total_items_min" in params:
        query = query.filter(RoutePlan.total_item_count >= int(params["total_items_min"]))

    if "total_items_max" in params:
        query = query.filter(RoutePlan.total_item_count <= int(params["total_items_max"]))


    # query on orders table --------------------------------------------
    order_params = params.get( "orders" )
    if order_params:
        query = query.join( RoutePlan.orders )
        query = find_orders(
            params = order_params,
            ctx = ctx,
            query = query, 
        )
    #-----------------------------------------------

    # sort query by date_asc or date_desc -------------------------

    if params.get("sort") == 'date_asc':
        query = query.order_by( 
            RoutePlan.created_at.asc(),
            RoutePlan.id.asc()
        )
    else:
        query = query.order_by( 
            RoutePlan.created_at.desc(),
            RoutePlan.id.desc()
        )

    #----------------------------------------------------


    # pagination -------------------------

    query = apply_opaque_pagination_by_date(
        query = query,
        date_column = RoutePlan.created_at,
        id_column = RoutePlan.id,
        params = params,
        sort = params.get( "sort", 'date_desc')
    )

    #----------------------------------------------------
    
    return query.distinct()
