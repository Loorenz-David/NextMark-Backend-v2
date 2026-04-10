from collections import OrderedDict

from sqlalchemy import Float, cast
from sqlalchemy.orm import Query

from Delivery_app_BK.models import db, Order

from ...context import ServiceContext
from .find_orders import find_orders
from .serialize_order import serialize_orders

MAX_MARKERS = 1000


def _to_float(value):
    if value is None or value == "":
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _with_bounds(query: Query, params: dict):
    north = _to_float(params.get("north"))
    south = _to_float(params.get("south"))
    east = _to_float(params.get("east"))
    west = _to_float(params.get("west"))

    if None in (north, south, east, west):
        return None

    lat_expr = cast(Order.client_address["coordinates"]["lat"].astext, Float)
    lng_expr = cast(Order.client_address["coordinates"]["lng"].astext, Float)

    bounded = query.filter(
        lat_expr.isnot(None),
        lng_expr.isnot(None),
        lat_expr <= north,
        lat_expr >= south,
        lng_expr <= east,
        lng_expr >= west,
    )

    return bounded


def _build_marker_group_key(order: Order):
    coordinates = (order.client_address or {}).get("coordinates", {})
    lat = coordinates.get("lat")
    lng = coordinates.get("lng")
    if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
        return None

    if not (-90 <= float(lat) <= 90 and -180 <= float(lng) <= 180):
        return None

    return f"{float(lat):.5f},{float(lng):.5f}"


def list_order_markers(ctx: ServiceContext):
    base_query = db.session.query(Order)
    query_params = {
        key: value
        for key, value in dict(ctx.query_params).items()
        if key not in {"after_cursor", "before_cursor", "limit"}
    }

    query = find_orders(query_params, ctx, query=base_query)
    bounded_query = _with_bounds(query, query_params)
    if bounded_query is None:
        return {
            "markers": [],
            "order": serialize_orders([], ctx),
            "truncated": False,
        }

    found_orders = bounded_query.all()

    grouped_orders = OrderedDict()
    truncated = False
    seen_client_ids = set()

    for order in found_orders:
        if order.client_id in seen_client_ids:
            continue
        seen_client_ids.add(order.client_id)

        key = _build_marker_group_key(order)
        if not key:
            continue

        existing_group = grouped_orders.get(key)
        if existing_group is not None:
            existing_group["orders"].append(order)
            continue

        if len(grouped_orders) >= MAX_MARKERS:
            truncated = True
            continue

        coordinates = (order.client_address or {}).get("coordinates", {})
        grouped_orders[key] = {
            "id": f"order_group_marker:{key}",
            "coordinates": {
                "lat": float(coordinates["lat"]),
                "lng": float(coordinates["lng"]),
            },
            "orders": [order],
        }

    markers = []
    included_orders = []

    for marker in grouped_orders.values():
        orders = marker["orders"]
        primary_order = orders[0]
        included_orders.extend(orders)
        markers.append({
            "id": marker["id"],
            "coordinates": marker["coordinates"],
            "primary_order_client_id": primary_order.client_id,
            "order_client_ids": [order.client_id for order in orders],
            "count": len(orders),
        })

    return {
        "markers": markers,
        "order": serialize_orders(included_orders, ctx),
        "truncated": truncated,
    }
