"""
Recompute vehicle warnings for every route solution that contains a given order.

Called from item mutation commands (create / update / delete) so that vehicle
capacity warnings stay accurate whenever an order's total weight or volume changes.
"""

from __future__ import annotations

import logging
from typing import List

from Delivery_app_BK.models import db, RouteSolution, RouteSolutionStop, Order
from .apply_vehicle_warnings import apply_vehicle_warnings_to_route_solution

logger = logging.getLogger(__name__)


def recompute_vehicle_warnings_by_order(order: Order) -> None:
    """
    Find all route solutions that have a stop for *order* and re-apply vehicle
    warnings.  No-ops silently if the order has no stops or no vehicle is
    assigned to those route solutions.

    Does NOT commit — caller owns the session lifecycle.
    """
    if order is None or order.id is None:
        return

    # Find route solution ids that contain a stop for this order
    stop_rows = (
        db.session.query(RouteSolutionStop.route_solution_id)
        .filter(RouteSolutionStop.order_id == order.id)
        .distinct()
        .all()
    )
    if not stop_rows:
        return

    route_solution_ids = [row[0] for row in stop_rows if row[0] is not None]
    if not route_solution_ids:
        return

    for rs_id in route_solution_ids:
        route_solution: RouteSolution | None = db.session.get(RouteSolution, rs_id)
        if route_solution is None:
            continue

        vehicle = getattr(route_solution, "vehicle", None)
        if vehicle is None and route_solution.vehicle_id:
            from Delivery_app_BK.models.tables.infrastructure.vehicle import Vehicle
            vehicle = db.session.get(Vehicle, route_solution.vehicle_id)

        # Load all orders for this route solution for volume/weight aggregation
        order_ids = (
            db.session.query(RouteSolutionStop.order_id)
            .filter(RouteSolutionStop.route_solution_id == rs_id)
            .distinct()
            .all()
        )
        order_id_list = [r[0] for r in order_ids if r[0] is not None]
        orders: List[Order] = (
            db.session.query(Order).filter(Order.id.in_(order_id_list)).all()
            if order_id_list
            else []
        )

        apply_vehicle_warnings_to_route_solution(
            route_solution=route_solution,
            vehicle=vehicle,
            orders=orders,
            flush=False,
        )
        logger.debug(
            "recompute_vehicle_warnings_by_order order_id=%s route_solution_id=%s",
            order.id,
            rs_id,
        )
