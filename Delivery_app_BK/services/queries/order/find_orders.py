from typing import Dict, Any
from sqlalchemy.orm import Query

from Delivery_app_BK.models import db, Order, Item, DeliveryPlan, OrderDeliveryWindow, OrderState
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team
from Delivery_app_BK.services.queries.utils  import parsed_string_to_list
from sqlalchemy import func, String, false, or_

from ...context import ServiceContext
from ...utils import to_datetime
from ..utils import apply_opaque_pagination_by_date, str_to_bool
from ..item.find_items import find_items


def find_orders ( 
        params: Dict[str, Any],
        ctx: ServiceContext ,
        query: Query | None = None
):
  
    query = query or db.session.query( Order )

    if model_requires_team( Order ) and ctx.inject_team_id:
        params = inject_team_id( params, ctx )
    
  
    if "team_id" in params:
        query = query.filter( Order.team_id == params.get( "team_id" ) )

    if "show_archived" in params and str_to_bool(params["show_archived"]):
        query = query.filter(Order.archive_at.isnot(None))
    else:
        query = query.filter(Order.archive_at.is_(None))

    string_filter_map = {
        # ---------------- ORDER FIELDS ----------------
        "reference_number": {
            "column": Order.reference_number,
            "join": None,
        },
        "order_scalar_id": {
            "column": Order.order_scalar_id.cast(String),
            "join": None,
        },
        "external_source": {
            "column": Order.external_source,
            "join": None,
        },
        "tracking_number": {
            "column": Order.tracking_number,
            "join": None,
        },
        "client_email": {
            "column": Order.client_email,
            "join": None,
        },
        "client_address": {
            "column": Order.client_address.cast(String),
            "join": None,
            "full_text": True,
        },
        "client_name":{
            "column":(
                Order.client_first_name,
                Order.client_last_name
            ),
            "join":None
        },
        # ---------------- JSON PHONE ----------------
        # Stored as { prefix: string, number: string }
        "client_phone": {
            "column": (
                Order.client_primary_phone["number"].astext,
                Order.client_secondary_phone["number"].astext,
            ),
            "join": None,
        },
        # ---------------- ITEM FIELDS ----------------
        "article_number": {
            "column": Item.article_number,
            "join": Order.items,
        },
        "item_type": {
            "column": Item.item_type,
            "join": Order.items,
        },
        # ---------------- DELIVERY PLAN ----------------
        "plan_label": {
            "column": DeliveryPlan.label,
            "join": Order.delivery_plan,
        },
        "plan_type": {
            "column": Order.order_plan_objective,
            "join": None,
        },
    }

    trimmed_query = str(params.get("q") or "").strip()
    incoming_string_columns = set()

    if "s" in params:
        parsed = parsed_string_to_list(params["s"], ctx)
      
        incoming_string_columns = set(parsed)

   
    if trimmed_query:
        if incoming_string_columns:
            active_columns = incoming_string_columns
        else:
            active_columns = string_filter_map.keys()
    else:
        active_columns = set()

    joined_relations = set()
    filters = []
   
    if trimmed_query and active_columns:
        pattern = f"%{trimmed_query}%"

        for key in active_columns:
            config = string_filter_map.get(key)
            if not config:
                continue

            column = config["column"]
            join_target = config.get("join")

            # SAFE JOIN (only once)
            if join_target and join_target not in joined_relations:
                query = query.outerjoin(join_target)
                joined_relations.add(join_target)

            # FULL TEXT SEARCH
            if config.get("full_text"):
                filters.append(
                    func.to_tsvector("simple", column).op("@@")(
                        func.plainto_tsquery("simple", trimmed_query)
                    )
                )
                continue

            # MULTI COLUMN SEARCH (client_phone)
            if isinstance(column, tuple):
                filters.append(
                    or_(*[col.ilike(pattern) for col in column])
                )
            else:
                filters.append(column.ilike(pattern))

        if filters:
            query = query.filter(or_(*filters))


    if "schedule_order" in params:
        query = query.filter(Order.delivery_plan_id.isnot(None))
    if "unschedule_order" in params:
        query = query.filter(Order.delivery_plan_id.is_(None))
            

    if "earliest_delivery_date" in params:
        earliest_delivery_date = to_datetime( params.get( "earliest_delivery_date" ) )
        window_subquery = (
            db.session.query(OrderDeliveryWindow.id)
            .filter(
                OrderDeliveryWindow.order_id == Order.id,
                OrderDeliveryWindow.start_at >= earliest_delivery_date,
            )
            .exists()
        )
        query = query.filter(window_subquery)

    if "latest_delivery_date" in params:
        latest_delivery_date = to_datetime ( params.get( "latest_delivery_date" ) )
        window_subquery = (
            db.session.query(OrderDeliveryWindow.id)
            .filter(
                OrderDeliveryWindow.order_id == Order.id,
                OrderDeliveryWindow.end_at <= latest_delivery_date,
            )
            .exists()
        )
        query = query.filter(window_subquery)

    if "creation_date_from" in params:
        creation_date_from = to_datetime( params.get("creation_date_from" ) )
        query = query.filter( Order.creation_date >= creation_date_from )
        
    if "creation_date_to" in params:
        creation_date_to = to_datetime( params.get("creation_date_to" ) )
        query = query.filter( Order.creation_date <= creation_date_to )

    state_filter_values = _resolve_order_state_filter_values(params)
    if state_filter_values:
        order_state_ids = []
        state_names = []
        for value in state_filter_values:
            if isinstance(value, int):
                order_state_ids.append(value)
                continue

            stripped = str(value).strip()
            if not stripped:
                continue
            if stripped.isdigit():
                order_state_ids.append(int(stripped))
            else:
                state_names.append(stripped)

        if state_names:
            resolved_ids = (
                db.session.query(OrderState.id)
                .filter(OrderState.name.in_(state_names))
                .all()
            )
            order_state_ids.extend(state_id for (state_id,) in resolved_ids)

        deduped_ids = list(dict.fromkeys(order_state_ids))
        if deduped_ids:
            query = query.filter(Order.order_state_id.in_(deduped_ids))
        else:
            query = query.filter(false())

    plan_type_filter_values = _resolve_plan_type_filter_values(params, ctx)
    if plan_type_filter_values:
        normalized_plan_types = []
        for value in plan_type_filter_values:
            stripped = str(value).strip()
            if stripped:
                normalized_plan_types.append(stripped)

        deduped_plan_types = list(dict.fromkeys(normalized_plan_types))
        if deduped_plan_types:
            query = query.filter(Order.order_plan_objective.in_(deduped_plan_types))
        else:
            query = query.filter(false())


    #----------------------------------------------------


    #  query on items table -------------------------

    item_params = params.get( "items" )
    if item_params:
        item_params["q"] = trimmed_query

        if Order.items not in joined_relations:
            query = query.join(Order.items)
            joined_relations.add(Order.items)

        query = find_items(
            params = item_params,
            ctx = ctx,
            query = query,
        )

    #----------------------------------------------------



    # sort query by date_asc or date_desc -------------------------

    if params.get("sort") == 'date_asc':
        query = query.order_by( 
            Order.creation_date.asc(),
            Order.id.asc()
        )
    else:
        query = query.order_by( 
            Order.creation_date.desc(),
            Order.id.desc()
        )
    #----------------------------------------------------



    # pagination -------------------------
    query = apply_opaque_pagination_by_date(
        query = query,
        date_column = Order.creation_date,
        id_column = Order.id,
        params = params,
        sort = params.get( "sort", 'date_desc')
    )

   

    #----------------------------------------------------
    return query.distinct()


def _resolve_order_state_filter_values(params: Dict[str, Any]) -> list[Any]:
    for key in ("order_state_id", "order_state"):
        if key not in params:
            continue
        values = params.get(key)
        if isinstance(values, (list, tuple)):
            return list(values)
        return [values]
    return []


def _resolve_plan_type_filter_values(params: Dict[str, Any], ctx: ServiceContext) -> list[Any]:
    query_params = getattr(ctx, "query_params", None)
    if query_params is not None and hasattr(query_params, "getlist"):
        values = query_params.getlist("plan_type[]")
        if values:
            return values

        values = query_params.getlist("plan_type")
        if values:
            return values

    if "plan_type[]" in params:
        values = params.get("plan_type[]")
        if isinstance(values, (list, tuple)):
            return list(values)
        return [values]

    if "plan_type" not in params:
        return []

    values = params.get("plan_type")
    if isinstance(values, (list, tuple)):
        return list(values)

    parsed_values = parsed_string_to_list(values, ctx)
    if isinstance(parsed_values, list):
        return parsed_values

    return [values]
