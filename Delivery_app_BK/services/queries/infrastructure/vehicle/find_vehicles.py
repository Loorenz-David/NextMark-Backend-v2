from typing import Dict, Any
from sqlalchemy.orm import Query
from sqlalchemy import String, or_

from Delivery_app_BK.models import db, Vehicle
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team
from Delivery_app_BK.services.queries.utils import parsed_string_to_list
from ....context import ServiceContext
from ...utils import apply_pagination_by_id


def find_vehicles(
    params: Dict[str, Any],
    ctx: ServiceContext,
    query: Query | None = None,
):
    """
    Find vehicles with Shopify-style filtering.
    
    Parameters:
    -----------
    q : str
        General search term across registration_number, label, status, fuel_type, travel_mode
        Automatically narrows to specified columns via `s` parameter, or all columns if not specified
    
    s : str | list
        Comma-separated string or JSON array of column names to search within
        Valid columns: registration_number, label, fuel_type, travel_mode, status
        Only applied when `q` is provided
    
    team_id : int
        Team scope (auto-injected from context)
    
    client_id : str
        Filter by client_id
    
    travel_mode : str
        Exact filter by travel_mode
    
    status : str
        Exact filter by status (idle, in_route, loading, offline, maintenance)
    
    fuel_type : str
        Exact filter by fuel_type
    
    is_active : bool
        Filter by is_active status
    
    home_facility_id : int
        Filter by home facility
    
    sort : str
        Sort order: id_asc, id_desc (default: id_desc)
    """
    
    query = query or db.session.query(Vehicle)

    if model_requires_team(Vehicle) and ctx.inject_team_id:
        params = inject_team_id(params, ctx)

    if "team_id" in params:
        query = query.filter(Vehicle.team_id == params.get("team_id"))

    # String filter map: maps column names to database columns
    # These columns are searchable via the `q` parameter
    string_filter_map = {
        "registration_number": {
            "column": Vehicle.registration_number,
            "join": None,
        },
        "label": {
            "column": Vehicle.label,
            "join": None,
        },
        "fuel_type": {
            "column": Vehicle.fuel_type,
            "join": None,
        },
        "travel_mode": {
            "column": Vehicle.travel_mode,
            "join": None,
        },
        "status": {
            "column": Vehicle.status,
            "join": None,
        },
    }

    # Parse general search query
    trimmed_query = str(params.get("q") or "").strip()
    incoming_string_columns = set()
    
    # Parse `s` parameter (column narrowing)
    if "s" in params:
        parsed = parsed_string_to_list(params["s"], ctx)
        incoming_string_columns = set(parsed)
    
    # Determine which columns to search
    if trimmed_query:
        if incoming_string_columns:
            # Use only the specified columns
            active_columns = incoming_string_columns
        else:
            # Search all string columns by default
            active_columns = string_filter_map.keys()
    else:
        active_columns = set()
    
    # Build `q` search filters
    filters = []
    if trimmed_query and active_columns:
        pattern = f"%{trimmed_query}%"
        
        for key in active_columns:
            config = string_filter_map.get(key)
            if not config:
                continue
            
            column = config["column"]
            filters.append(column.ilike(pattern))
        
        if filters:
            query = query.filter(or_(*filters))

    # Additional field filters (exact match or specific logic)
    if "client_id" in params:
        query = query.filter(Vehicle.client_id == params.get("client_id"))

    if "travel_mode" in params:
        query = query.filter(Vehicle.travel_mode == params.get("travel_mode"))

    if "is_active" in params:
        raw = params.get("is_active")
        query = query.filter(Vehicle.is_active == (str(raw).lower() == "true"))

    if "status" in params:
        query = query.filter(Vehicle.status == params.get("status"))

    if "fuel_type" in params:
        query = query.filter(Vehicle.fuel_type == params.get("fuel_type"))

    if "home_facility_id" in params:
        query = query.filter(Vehicle.home_facility_id == params.get("home_facility_id"))

    # Sorting
    sort = params.get("sort", "id_desc")
    if sort == "id_asc":
        query = query.order_by(Vehicle.id.asc())
    else:
        query = query.order_by(Vehicle.id.desc())

    # Pagination
    query = apply_pagination_by_id(
        query,
        id_column=Vehicle.id,
        params=params,
        sort=sort,
    )

    return query
