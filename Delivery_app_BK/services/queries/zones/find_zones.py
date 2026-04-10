from typing import Dict, Any
from sqlalchemy.orm import Query
from sqlalchemy import String, or_

from Delivery_app_BK.models import db, Zone
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team
from Delivery_app_BK.services.queries.utils import parsed_string_to_list
from ...context import ServiceContext
from ..utils import apply_pagination_by_id


def find_zones(
    params: Dict[str, Any],
    ctx: ServiceContext,
    query: Query | None = None,
):
    """
    Find zones with Shopify-style filtering.
    
    Parameters:
    -----------
    q : str
        General search term across name, city_key, zone_type
        Automatically narrows to specified columns via `s` parameter, or all columns if not specified
    
    s : str | list
        Comma-separated string or JSON array of column names to search within
        Valid columns: name, city_key, zone_type
        Only applied when `q` is provided
    
    version_id : int
        Filter by zone_version_id
    
    zone_type : str
        Filter by zone_type (bootstrap, system, user)
    
    is_active : bool
        Filter by is_active status
    
    city_key : str
        Filter by city_key
    
    sort : str
        Sort order: id_asc, id_desc (default: id_desc)
    """
    
    query = query or db.session.query(Zone)
    
    if model_requires_team(Zone) and ctx.inject_team_id:
        params = inject_team_id(params, ctx)
    
    # Team scope (required)
    if "team_id" in params:
        query = query.filter(Zone.team_id == params.get("team_id"))
    
    # String filter map: maps column names to database columns
    # These columns are searchable via the `q` parameter
    string_filter_map = {
        "name": {
            "column": Zone.name,
            "join": None,
        },
        "city_key": {
            "column": Zone.city_key,
            "join": None,
        },
        "zone_type": {
            "column": Zone.zone_type,
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
    
    # Additional field filters
    if "version_id" in params:
        query = query.filter(Zone.zone_version_id == params.get("version_id"))
    
    if "zone_type" in params:
        query = query.filter(Zone.zone_type == params.get("zone_type"))
    
    if "is_active" in params:
        raw = params.get("is_active")
        is_active = str(raw).lower() == "true"
        query = query.filter(Zone.is_active == is_active)
    
    if "city_key" in params:
        city_key = params.get("city_key").strip()
        query = query.filter(Zone.city_key.ilike(f"%{city_key}%"))
    
    # Sorting
    sort = params.get("sort", "id_desc")
    if sort == "id_asc":
        query = query.order_by(Zone.id.asc())
    else:
        query = query.order_by(Zone.id.desc())
    
    # Pagination
    query = apply_pagination_by_id(
        query,
        id_column=Zone.id,
        params=params,
        sort=sort,
    )
    
    return query
