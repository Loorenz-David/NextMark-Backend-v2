"""
geometry_utils.py — pure-Python spatial helpers for route corridor analysis.

All coordinates are (lat, lng) float tuples.
All distances are in meters unless otherwise noted.
"""
from __future__ import annotations
import math


# ── Haversine distance ────────────────────────────────────────────────────────

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return the great-circle distance in meters between two WGS-84 points."""
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lng / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


# ── Centroid + radius corridor ────────────────────────────────────────────────

def centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
    """Return the geographic centroid (mean lat, mean lng) of a point list."""
    if not points:
        raise ValueError("Cannot compute centroid of empty point list.")
    lat = sum(p[0] for p in points) / len(points)
    lng = sum(p[1] for p in points) / len(points)
    return lat, lng


def max_radius_m(center: tuple[float, float], points: list[tuple[float, float]]) -> float:
    """Return the maximum distance from center to any point in the list (meters)."""
    if not points:
        return 0.0
    return max(haversine_m(center[0], center[1], p[0], p[1]) for p in points)


def point_within_corridor(
    candidate: tuple[float, float],
    stop_points: list[tuple[float, float]],
    buffer_m: float,
) -> bool:
    """
    Return True if *candidate* falls within the corridor of *stop_points*.

    Corridor is defined as a circle centred on the centroid of stop_points,
    with radius = max_radius_from_centroid + buffer_m.
    """
    if not stop_points:
        return False
    center = centroid(stop_points)
    route_radius = max_radius_m(center, stop_points)
    distance_to_center = haversine_m(center[0], center[1], candidate[0], candidate[1])
    return distance_to_center <= (route_radius + buffer_m)


# ── Detour estimation ─────────────────────────────────────────────────────────

def cheapest_insertion(
    stop_points: list[tuple[float, float]],
    candidate: tuple[float, float],
) -> dict:
    """
    Find the cheapest insertion position for *candidate* in an ordered stop list.

    Evaluates cost = dist(stop[i], candidate) + dist(candidate, stop[i+1])
                     - dist(stop[i], stop[i+1])
    for every consecutive pair.

    Returns:
        {
            "best_index":           int,    # insert before this stop index
            "detour_meters":        float,  # additional distance added
            "dist_to_prev_m":       float,
            "dist_to_next_m":       float,
        }
    If there is 0 or 1 stop, returns insertion at the end.
    """
    if len(stop_points) == 0:
        return {"best_index": 0, "detour_meters": 0.0, "dist_to_prev_m": 0.0, "dist_to_next_m": 0.0}

    if len(stop_points) == 1:
        d = haversine_m(stop_points[0][0], stop_points[0][1], candidate[0], candidate[1])
        return {"best_index": 1, "detour_meters": d, "dist_to_prev_m": d, "dist_to_next_m": 0.0}

    best_index = 1
    best_cost = float("inf")
    best_to_prev = 0.0
    best_to_next = 0.0

    for i in range(len(stop_points) - 1):
        p0, p1 = stop_points[i], stop_points[i + 1]
        d_prev = haversine_m(p0[0], p0[1], candidate[0], candidate[1])
        d_next = haversine_m(candidate[0], candidate[1], p1[0], p1[1])
        d_orig = haversine_m(p0[0], p0[1], p1[0], p1[1])
        cost = d_prev + d_next - d_orig
        if cost < best_cost:
            best_cost = cost
            best_index = i + 1
            best_to_prev = d_prev
            best_to_next = d_next

    # Also try appending at the end
    last = stop_points[-1]
    d_append = haversine_m(last[0], last[1], candidate[0], candidate[1])
    if d_append < best_cost:
        best_cost = d_append
        best_index = len(stop_points)
        best_to_prev = d_append
        best_to_next = 0.0

    return {
        "best_index": best_index,
        "detour_meters": max(0.0, best_cost),
        "dist_to_prev_m": best_to_prev,
        "dist_to_next_m": best_to_next,
    }


# ── Speed / tolerance conversion ──────────────────────────────────────────────

AVG_CITY_SPEED_MPS = 13.9  # ~50 km/h


def eta_tolerance_to_buffer_m(eta_tolerance_seconds: int) -> float:
    """
    Convert an ETA tolerance (seconds) to a spatial buffer radius (meters).
    Uses AVG_CITY_SPEED_MPS as the conversion factor.
    Minimum buffer is 300 m.
    """
    radius = eta_tolerance_seconds * AVG_CITY_SPEED_MPS
    return max(300.0, radius)


def meters_to_seconds(meters: float, speed_mps: float = AVG_CITY_SPEED_MPS) -> int:
    """Estimate travel time in seconds for a given distance at the given speed."""
    if speed_mps <= 0:
        return 0
    return int(meters / speed_mps)
