from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from Delivery_app_BK.directions.domain.models import (
    DirectionsRequest,
    DirectionsResult,
    DirectionsStopResult,
)


class GoogleDirectionsRequestMapper:
    @staticmethod
    def build_request(request: DirectionsRequest) -> Tuple[Dict[str, Any], str]:
        payload: Dict[str, Any] = {
            "origin": _lat_lng(request.origin),
            "destination": _lat_lng(request.destination),
            "intermediates": [
                {
                    "location": _lat_lng(stop.location)["location"],
                    "vehicle_stopover": True,
                }
                for stop in request.intermediates
            ],
            "travel_mode": _travel_mode(request.travel_mode),
            "routing_preference": "TRAFFIC_AWARE"
            if request.consider_traffic
            else "TRAFFIC_UNAWARE",
            "compute_alternative_routes": False,
            "route_modifiers": _route_modifiers(request.route_modifiers),
            "polyline_quality": "OVERVIEW",
            "polyline_encoding": "ENCODED_POLYLINE",
        }

        
        if request.departure_time:
            now = datetime.now(timezone.utc)
            departure = request.departure_time
            if departure.tzinfo is None:
                departure = departure.replace(tzinfo=timezone.utc)
            if departure <= now:
                departure = now + timedelta(minutes=1)
            payload["departure_time"] = _format_time(departure)
        field_mask = (
            "routes.duration,"
            "routes.distance_meters,"
            "routes.legs.duration,"
            "routes.legs.distance_meters,"
            "routes.legs.polyline.encoded_polyline"
        )
        
        return payload, field_mask


class GoogleDirectionsResponseMapper:
    @staticmethod
    def parse_response(response: Any, request: DirectionsRequest) -> DirectionsResult:
        routes = getattr(response, "routes", None) or []
        if not routes:
            return DirectionsResult(
                total_distance_meters=0,
                total_duration_seconds=0,
                leg_polylines=[],
                start_time=request.departure_time,
                end_time=request.departure_time,
                stop_results=[],
            )

        route = routes[0]
        duration_seconds = _duration_to_seconds(getattr(route, "duration", None))
        distance_meters = int(getattr(route, "distance_meters", 0) or 0)
        legs = getattr(route, "legs", None) or []
        leg_polylines: List[Optional[str]] = []
        stop_results: List[DirectionsStopResult] = []
        departure_time = request.departure_time
        current_time = departure_time

        for idx, stop in enumerate(request.intermediates):
            if idx < len(legs):
                leg = legs[idx]
                leg_duration = _duration_to_seconds(getattr(leg, "duration", None))
                leg_distance = int(getattr(leg, "distance_meters", 0) or 0)
            else:
                leg_duration = 0
                leg_distance = 0
                leg_polyline = None

            if idx < len(legs):
                leg_polyline = None
                if getattr(leg, "polyline", None):
                    leg_polyline = getattr(leg.polyline, "encoded_polyline", None)
            leg_polylines.append(leg_polyline)

            if current_time:
                current_time = current_time + timedelta(seconds=leg_duration)
            stop_results.append(
                DirectionsStopResult(
                    order_id=stop.order_id,
                    arrival_time=current_time,
                    travel_duration_seconds=leg_duration,
                    distance_meters=leg_distance,
                )
            )
            if current_time and stop.service_duration_seconds:
                current_time = current_time + timedelta(
                    seconds=stop.service_duration_seconds
                )

        end_time = current_time
        if len(legs) > len(request.intermediates) and current_time:
            last_leg = legs[len(request.intermediates)]
            if getattr(last_leg, "polyline", None):
                leg_polylines.append(
                    getattr(last_leg.polyline, "encoded_polyline", None)
                )
            else:
                leg_polylines.append(None)
            current_time = current_time + timedelta(
                seconds=_duration_to_seconds(getattr(last_leg, "duration", None))
            )
            end_time = current_time
        elif len(legs) > len(request.intermediates):
            last_leg = legs[len(request.intermediates)]
            if getattr(last_leg, "polyline", None):
                leg_polylines.append(
                    getattr(last_leg.polyline, "encoded_polyline", None)
                )
            else:
                leg_polylines.append(None)

        return DirectionsResult(
            total_distance_meters=distance_meters,
            total_duration_seconds=duration_seconds,
            leg_polylines=leg_polylines,
            start_time=request.departure_time,
            end_time=end_time,
            stop_results=stop_results,
        )


def _format_time(value: Optional[datetime]) -> Optional[datetime]:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0)


def _lat_lng(location: Dict[str, float]) -> Dict[str, Any]:
    return {
        "location": {
            "lat_lng": {
                "latitude": location["latitude"],
                "longitude": location["longitude"],
            }
        }
    }


def _route_modifiers(route_modifiers: Dict[str, bool]) -> Dict[str, bool]:
    return {
        "avoid_tolls": bool(route_modifiers.get("avoid_tolls")),
        "avoid_highways": bool(route_modifiers.get("avoid_highways")),
        "avoid_ferries": bool(route_modifiers.get("avoid_ferries")),
    }


def _travel_mode(value: str) -> str:
    normalized = str(value or "").upper()
    if normalized in {"DRIVE", "DRIVING"}:
        return "DRIVE"
    return "DRIVE"


def _duration_to_seconds(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if hasattr(value, "seconds"):
        return int(value.seconds)
    if isinstance(value, dict):
        return int(value.get("seconds", 0))
    try:
        parsed = str(value).rstrip("s")
        return int(float(parsed))
    except (TypeError, ValueError):
        return 0
