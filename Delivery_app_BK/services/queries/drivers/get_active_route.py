from sqlalchemy.orm import selectinload

from Delivery_app_BK.errors import NotFound, PermissionDenied, ValidationFailed
from Delivery_app_BK.models import Order, RouteGroup, RouteSolution, db
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.drivers.serialize_active_routes import serialize_active_route
from Delivery_app_BK.services.queries.order.serialize_order import serialize_orders_with_items
from Delivery_app_BK.services.queries.route_solutions import serialize_route_solution_stops
from Delivery_app_BK.services.utils import require_team_id


def get_active_route(route_id: int, ctx: ServiceContext):
    if route_id is None or route_id <= 0:
        raise ValidationFailed("route_id is required.")

    team_id = require_team_id(ctx)
    route = (
        db.session.query(RouteSolution)
        .options(
            selectinload(RouteSolution.route_group).selectinload(
                RouteGroup.route_plan
            ),
            selectinload(RouteSolution.stops),
        )
        .filter(
            RouteSolution.team_id == team_id,
            RouteSolution.id == route_id,
            RouteSolution.is_selected.is_(True),
        )
        .one_or_none()
    )

    if route is None:
        raise NotFound(f"Active route with id: {route_id} does not exist.")

    if ctx.app_scope == "driver" and route.driver_id != ctx.user_id:
        raise PermissionDenied("You are not authorized to access this route.")

    stops = list(route.stops or [])
    order_ids = {
        stop.order_id
        for stop in stops
        if stop.order_id is not None
    }

    orders = []
    if order_ids:
        orders = (
            db.session.query(Order)
            .options(
                selectinload(Order.items),
                selectinload(Order.delivery_windows),
                selectinload(Order.order_cases),
            )
            .filter(
                Order.team_id == team_id,
                Order.id.in_(order_ids),
            )
            .all()
        )

    return {
        "route": serialize_active_route(route, ctx),
        "orders": serialize_orders_with_items(orders, ctx),
        "stops": serialize_route_solution_stops(stops, ctx),
    }
