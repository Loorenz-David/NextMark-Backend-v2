from __future__ import annotations

from Delivery_app_BK.models import RouteSolution, RouteSolutionStop
from Delivery_app_BK.services.commands.order.create_serializers import (
    serialize_created_order_stops,
)
from Delivery_app_BK.services.queries.route_solutions.serialize_route_solutions import (
    serialize_route_solution,
)


def merge_bundle_payload(
    bundle_by_order_id: dict[int, dict],
    order_id: int,
    *,
    stops: list[RouteSolutionStop] | None = None,
    route_solutions: list[RouteSolution] | None = None,
) -> None:
    if not order_id:
        return

    bundle = bundle_by_order_id.setdefault(order_id, {})
    if stops:
        incoming_stops = serialize_created_order_stops(_dedupe_stops(stops))
        existing_stops = bundle.get("order_stops") or []
        bundle["order_stops"] = _merge_serialized_stops(existing_stops, incoming_stops)

    if route_solutions:
        incoming_routes = [serialize_route_solution(route) for route in _dedupe_routes(route_solutions)]
        existing_routes = bundle.get("route_solution") or []
        bundle["route_solution"] = _merge_serialized_routes(existing_routes, incoming_routes)



def _merge_serialized_stops(existing: list[dict], incoming: list[dict]) -> list[dict]:
    merged = list(existing or []) + list(incoming or [])
    deduped: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for stop in merged:
        key = _payload_key(stop)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(stop)

    return sorted(
        deduped,
        key=lambda stop: (
            stop.get("stop_order") if stop.get("stop_order") is not None else 10**9,
            stop.get("id") if stop.get("id") is not None else 10**9,
            stop.get("client_id") or "",
        ),
    )


def _merge_serialized_routes(existing: list[dict], incoming: list[dict]) -> list[dict]:
    merged = list(existing or []) + list(incoming or [])
    deduped: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for route in merged:
        key = _payload_key(route)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(route)
    return deduped


def _payload_key(payload: dict) -> tuple[str, str]:
    payload_id = payload.get("id")
    if payload_id is not None:
        return ("id", str(payload_id))
    return ("client_id", str(payload.get("client_id")))


def _dedupe_stops(stops: list[RouteSolutionStop]) -> list[RouteSolutionStop]:
    deduped: list[RouteSolutionStop] = []
    seen: set[tuple[str, str]] = set()
    for stop in stops or []:
        stop_id = getattr(stop, "id", None)
        client_id = getattr(stop, "client_id", None)
        key = ("id", str(stop_id)) if stop_id is not None else ("client_id", str(client_id))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(stop)
    return deduped


def _dedupe_routes(route_solutions: list[RouteSolution]) -> list[RouteSolution]:
    deduped: list[RouteSolution] = []
    seen: set[tuple[str, str]] = set()
    for route in route_solutions or []:
        route_id = getattr(route, "id", None)
        client_id = getattr(route, "client_id", None)
        key = ("id", str(route_id)) if route_id is not None else ("client_id", str(client_id))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(route)
    return deduped
