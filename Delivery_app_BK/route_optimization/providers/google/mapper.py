from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import re

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.route_optimization.domain.models import (
    OptimizationRequest,
    OptimizationResult,
    SkippedShipment,
    StopResult,
)



class GoogleRequestMapper:
    @staticmethod
    def build_request(parent: str, request: OptimizationRequest) -> Dict[str, Any]:
        shipments: List[Dict[str, Any]] = []

        for shipment in request.shipments:
            
            delivery: Dict[str, Any] = {
                "arrival_waypoint": {
                    "location": {
                        "lat_lng": {
                            "latitude": shipment.location["latitude"],
                            "longitude": shipment.location["longitude"],
                        }
                    }
                }
            }
            if shipment.service_duration_seconds:
                delivery["duration"] = f"{int(shipment.service_duration_seconds)}s"

            time_windows = []
            for window in shipment.time_windows:
                start_time = _format_time(window.start_time)
                end_time = _format_time(window.end_time)
                if start_time or end_time:
                    entry: Dict[str, str] = {}
                    if start_time:
                        entry["start_time"] = start_time
                    if end_time:
                        entry["end_time"] = end_time
                    time_windows.append(entry)
            if time_windows:
                delivery["time_windows"] = time_windows

            shipments.append(
                {
                    "label": shipment.label,
                    "deliveries": [delivery],
                }
            )

        vehicle = {
            "label": f"vehicle-{request.route_group_id}",
            "start_location": request.start_coordinates,
            "end_location": request.end_coordinates,
            "travel_mode": request.travel_mode,
            "cost_per_kilometer": request.cost_per_kilometer,
            "route_modifiers": dict(request.route_modifiers),
        }

        model: Dict[str, Any] = {
            "shipments": shipments,
            "vehicles": [vehicle],
        }

        if request.global_start_time:
            model["global_start_time"] = _format_time(request.global_start_time)
        if request.global_end_time:
            model["global_end_time"] = _format_time(request.global_end_time)

        payload: Dict[str, Any] = {
            "parent": parent,
            "model": model,
            "populate_transition_polylines": bool(
                request.populate_transition_polylines
            ),
            "consider_road_traffic": bool(request.consider_traffic),
        }

        if request.objectives:
            payload["model"]["objectives"] = request.objectives

        if request.injected_routes:
            payload["injected_first_solution_routes"] = request.injected_routes
            payload["interpret_injected_solutions_using_labels"] = (
                request.interpret_injected_solutions_using_labels
            )
      
        return payload


class GoogleResponseMapper:
    @staticmethod
    def parse_response(
        response_dict: Dict[str, Any], request: OptimizationRequest
    ) -> OptimizationResult:
        
        
        routes = response_dict.get("routes", [])
        if not routes:
            raise ValidationFailed("Route Optimization API returned no routes.")

        route = routes[0]
        visits = route.get("visits", [])
        transitions = route.get("transitions", [])
        route_metrics = route.get("metrics", {}) if isinstance(route.get("metrics"), dict) else {}

        total_distance = 0
        total_duration = 0
        polyline_parts: List[str] = []
        
        for idx, transition in enumerate(transitions):
           
            if not isinstance(transition, dict):
                continue

            transition_duration = _seconds_from_duration(transition.get("travel_duration"))
            travel_distance = int(transition.get("travel_distance_meters", 0))
            total_distance += travel_distance
            total_duration += transition_duration
            if request.populate_transition_polylines:
                transition_polyline = transition.get("route_polyline")
                encoded: str | None = None
                if isinstance(transition_polyline, dict):
                    points = transition_polyline.get("points")
                    if points:
                        encoded = points
                elif isinstance(transition_polyline, str):
                    encoded = transition_polyline
                polyline_parts.append(encoded)

        if total_distance <= 0:
            total_distance = int(route_metrics.get("travel_distance_meters", 0) or 0)

        if total_duration <= 0:
            total_duration = _seconds_from_duration(route_metrics.get("total_duration"))

        stops: List[StopResult] = []
        for idx, visit in enumerate(visits):
            shipment_label = _parse_shipment_label(visit)
            if shipment_label is None:
                continue
            arrival_time = _parse_time(visit.get("arrival_time") or visit.get("start_time"))
            stops.append(
                StopResult(
                    shipment_label=shipment_label,
                    stop_order=idx + 1,
                    expected_arrival_time=arrival_time,
                    in_range=True,
                )
            )

        skipped: List[SkippedShipment] = []
        for entry in response_dict.get("skipped_shipments", []):
            shipment_label = _parse_shipment_label(entry)
            if shipment_label is None:
                continue
            skipped.append(
                SkippedShipment(shipment_label=shipment_label, reason=entry.get("reasons"))
            )

        expected_start = (
            _parse_time(route.get("vehicle_start_time"))
            or _parse_time(visits[0].get("arrival_time") if visits else None)
        )
        expected_end = (
            _parse_time(route.get("vehicle_end_time"))
            or (
                _parse_time(
                    visits[-1].get("departure_time") or visits[-1].get("arrival_time")
                )
                if visits
                else None
            )
        )

        transition_polylines = None
       
        if request.populate_transition_polylines and polyline_parts:
            transition_polylines = polyline_parts
        

        return OptimizationResult(
            total_distance_meters=total_distance,
            total_duration_seconds=total_duration,
            expected_start_time=expected_start,
            expected_end_time=expected_end,
            transition_polylines=transition_polylines,
            stops=stops,
            skipped=skipped,
        )


def _format_time(value: Optional[datetime]) -> Optional[datetime]:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0)


def _seconds_from_duration(value: Any) -> int:
    if not value:
        return 0
    if isinstance(value, dict):
        seconds = int(value.get("seconds", 0))
        nanos = int(value.get("nanos", 0))
        return seconds + int(nanos / 1_000_000_000)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        return _extract_number(value)
    return 0

def _extract_number(value: str) -> int | None:
    match = re.search(r"\d+", value)
    return int(match.group()) if match else None

def _parse_shipment_label(payload: Dict[str, Any]) -> Optional[str]:
    label = payload.get("shipment_label") or payload.get("label")
    if not label:
        return None
    return str(label)


def _parse_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    parsed = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(parsed)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
