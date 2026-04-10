"""Point-to-zone resolution service for order coordinates."""

from dataclasses import dataclass
import math
from typing import Optional

from shapely.geometry import Point, shape

from Delivery_app_BK.models.tables.zones.zone import Zone


@dataclass
class ZoneResolution:
    """Resolution outcome for assigning a point to a zone."""

    zone: Optional[Zone]
    method: Optional[str]
    unassigned_reason: Optional[str] = None


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate haversine distance between two coordinates in kilometers.
    
    Args:
        lat1, lng1: First coordinate
        lat2, lng2: Second coordinate
        
    Returns:
        Distance in kilometers
    """
    R = 6371  # Earth radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)
    
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


def resolve_point_to_zone(
    zone_version_id: int,
    lat: float,
    lng: float,
    priority_types: list = None,
) -> ZoneResolution:
    """
    Resolve a point (lat/lng) to a zone within a specific zone version.

    Resolution strategy:
    1. Point-in-polygon match using GeoJSON geometry (primary)
    2. Centroid nearest-neighbor using haversine distance (fallback)
    
    Args:
        zone_version_id: Zone version to search in
        lat: Delivery latitude
        lng: Delivery longitude
        priority_types: List of zone_type values in priority order (e.g., ["user", "system", "bootstrap"])
                       Defaults to ["user", "system", "bootstrap"]
        
    Returns:
        ZoneResolution containing selected zone and assignment method.
    """
    if priority_types is None:
        priority_types = ["user", "system", "bootstrap"]

    query = Zone.query.filter(
        Zone.zone_version_id == zone_version_id,
        Zone.is_active == True,
    )

    zones = query.all()

    if not zones:
        return ZoneResolution(zone=None, method=None, unassigned_reason="no_candidate_zone")

    type_priority = {zone_type: idx for idx, zone_type in enumerate(priority_types)}

    point = Point(lng, lat)
    polygon_matches: list[Zone] = []
    has_polygon_data = False
    for zone in zones:
        geometry = zone.geometry
        if not geometry:
            continue
        has_polygon_data = True
        try:
            polygon = shape(geometry)
        except Exception:
            continue

        if polygon.is_empty:
            continue

        if polygon.contains(point):
            polygon_matches.append(zone)

    if polygon_matches:
        best_zone: Optional[Zone] = None
        best_priority = float("inf")
        best_distance = float("inf")

        for zone in polygon_matches:
            priority = type_priority.get(zone.zone_type, len(priority_types))
            lat_c = zone.centroid_lat
            lng_c = zone.centroid_lng
            distance = (
                haversine_distance(lat, lng, lat_c, lng_c)
                if lat_c is not None and lng_c is not None
                else float("inf")
            )

            if (
                priority < best_priority
                or (priority == best_priority and distance < best_distance)
            ):
                best_zone = zone
                best_priority = priority
                best_distance = distance

        if best_zone is not None:
            return ZoneResolution(zone=best_zone, method="polygon_direct")

    best_zone = None
    best_distance = float("inf")
    best_priority = float("inf")

    for zone in zones:
        priority = type_priority.get(zone.zone_type, len(priority_types))

        if priority > best_priority:
            continue

        lat_c = zone.centroid_lat
        lng_c = zone.centroid_lng
        if lat_c is None or lng_c is None:
            continue

        distance = haversine_distance(lat, lng, lat_c, lng_c)

        if priority < best_priority or (priority == best_priority and distance < best_distance):
            best_zone = zone
            best_distance = distance
            best_priority = priority

    if best_zone is not None:
        return ZoneResolution(zone=best_zone, method="centroid_fallback")

    return ZoneResolution(
        zone=None,
        method=None,
        unassigned_reason="polygon_miss" if has_polygon_data else "no_candidate_zone",
    )
