from Delivery_app_BK.models import RouteSolution, RouteSolutionStop, db
from Delivery_app_BK.socketio_instance import socketio
from Delivery_app_BK.sockets.contracts.realtime import SERVER_EVENT_REALTIME_EVENT
from Delivery_app_BK.sockets.rooms.names import build_route_orders_room


def resolve_route_ids_for_order(order_id: int | None, team_id: int | None) -> list[int]:
    if order_id is None or team_id is None:
        return []

    rows = (
        db.session.query(RouteSolutionStop.route_solution_id)
        .join(RouteSolution, RouteSolutionStop.route_solution_id == RouteSolution.id)
        .filter(
            RouteSolutionStop.order_id == order_id,
            RouteSolutionStop.team_id == team_id,
            RouteSolution.team_id == team_id,
            RouteSolution.is_selected.is_(True),
        )
        .distinct()
        .all()
    )

    return [route_id for (route_id,) in rows if isinstance(route_id, int)]


def emit_route_order_event(*, route_ids: list[int], envelope: dict) -> None:
    team_id = envelope.get("team_id")
    for route_id in route_ids:
        socketio.emit(
            SERVER_EVENT_REALTIME_EVENT,
            envelope,
            room=build_route_orders_room(team_id, route_id),
        )
