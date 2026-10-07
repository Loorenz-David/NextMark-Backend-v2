from collections.abc import Iterable
from datetime import datetime

from Delivery_app_BK.models import RouteSolution, RouteSolutionStop, db


def load_selected_order_arrivals(
    *,
    team_id: int,
    route_group_ids: Iterable[int],
) -> dict[int, datetime | None]:
    """{order_id: expected arrival} on the selected variant of each route
    group — the arrival a customer and driver actually go by."""
    group_ids = {group_id for group_id in route_group_ids if group_id is not None}
    if not group_ids:
        return {}

    rows = (
        db.session.query(RouteSolutionStop.order_id, RouteSolutionStop.expected_arrival_time)
        .join(RouteSolution, RouteSolutionStop.route_solution_id == RouteSolution.id)
        .filter(
            RouteSolution.team_id == team_id,
            RouteSolution.route_group_id.in_(group_ids),
            RouteSolution.is_selected.is_(True),
            RouteSolutionStop.order_id.isnot(None),
        )
        .all()
    )
    return {order_id: arrival for order_id, arrival in rows}
