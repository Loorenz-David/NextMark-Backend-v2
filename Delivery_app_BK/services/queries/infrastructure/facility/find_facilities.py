from typing import Dict, Any
from sqlalchemy.orm import Query
from sqlalchemy import String, or_, func

from Delivery_app_BK.models import db, Facility
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team
from Delivery_app_BK.services.queries.utils import parsed_string_to_list
from ....context import ServiceContext
from ...utils import apply_pagination_by_id


def find_facilities(
    params: Dict[str, Any],
    ctx: ServiceContext,
    query: Query | None = None,
):
    """
    Find facilities with Shopify-style filtering.
    
    Parameters:
    -----------
    q : str
        General search term across name, facility_type, client_id, property_location
        Automatically narrows to specified columns via `s` parameter, or all columns if not specified
    
    s : str | list
        Comma-separated string or JSON array of column names to search within
        Valid columns: name, facility_type, client_id, property_location
        Only applied when `q` is provided
    
    team_id : int
        Team scope (auto-injected from context)
    
    client_id : str
        Filter by client_id
    
    facility_type : str
        Exact filter by facility_type (warehouse, depot, hub, pickup_point)
    
    can_dispatch : bool
        Filter by can_dispatch capability
    
    can_receive_returns : bool
        Filter by can_receive_returns capability
    
    sort : str
        Sort order: id_asc, id_desc (default: id_desc)
    """
    
    query = query or db.session.query(Facility)
    
    if model_requires_team(Facility) and ctx.inject_team_id:
        params = inject_team_id(params, ctx)
    
    if "team_id" in params:
        query = query.filter(Facility.team_id == params.get("team_id"))
    
    # String filter map: maps column names to database columns
    # These columns are searchable via the `q` parameter
    string_filter_map = {
        "name": {
            "column": Facility.name,
            "join": None,
        },
        "facility_type": {
            "column": Facility.facility_type,
            "join": None,
        },
        "client_id": {
            "column": Facility.client_id,
            "join": None,
        },
        "property_location": {
            "column": Facility.property_location.cast(String),
            "join": None,
            "full_text": True,
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
        dialect_name = (query.session.bind.dialect.name if query.session.bind else "").lower()
        
        for key in active_columns:
            config = string_filter_map.get(key)
            if not config:
                continue
            
            column = config["column"]
            if config.get("full_text") and dialect_name == "postgresql":
                filters.append(
                    func.to_tsvector("simple", column).op("@@")(
                        func.plainto_tsquery("simple", trimmed_query)
                    )
                )
            else:
                filters.append(column.ilike(pattern))
        
        if filters:
            query = query.filter(or_(*filters))
    
    # Additional field filters (exact match or specific logic)
    if "client_id" in params:
        query = query.filter(Facility.client_id == params.get("client_id"))
    
    if "facility_type" in params:
        query = query.filter(Facility.facility_type == params.get("facility_type"))
    
    if "can_dispatch" in params:
        raw = params.get("can_dispatch")
        query = query.filter(Facility.can_dispatch == (str(raw).lower() == "true"))
    
    if "can_receive_returns" in params:
        raw = params.get("can_receive_returns")
        query = query.filter(Facility.can_receive_returns == (str(raw).lower() == "true"))
    
    # Sorting
    sort = params.get("sort", "id_desc")
    if sort == "id_asc":
        query = query.order_by(Facility.id.asc())
    else:
        query = query.order_by(Facility.id.desc())
    
    # Pagination
    query = apply_pagination_by_id(
        query,
        id_column=Facility.id,
        params=params,
        sort=sort,
    )
    
    return query
