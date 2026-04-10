"""
Zone attribution for RouteSolution.

Implements majority-stop strategy with 60% threshold:
1. Collect zone assignments from all order stops
2. If one zone covers >= 60% of stops → assign that zone
3. Otherwise → return (None, None) for fallback/bootstrap
"""
from typing import Optional, Tuple
from collections import Counter
import logging

logger = logging.getLogger(__name__)


def derive_route_zone(route_solution) -> Tuple[Optional[int], Optional[int]]:
    """Derive zone_id and zone_version_id for a route solution.
    
    Strategy:
    1. Collect zone assignments from all stops (via OrderZoneAssignment)
    2. Compute zone frequency (count stops per zone)
    3. If majority zone (>= 60% of stops) exists, return it
    4. Otherwise return (None, None) for bootstrap/unassigned fallback
    
    Args:
        route_solution: RouteSolution ORM instance
        
    Returns:
        Tuple of (zone_id, zone_version_id) or (None, None) if undetermined
    """
    try:
        from Delivery_app_BK.models import db
        from Delivery_app_BK.models.tables.zones.order_zone_assignment import OrderZoneAssignment
        
        if not route_solution or not route_solution.stops:
            return (None, None)
            
        stops = route_solution.stops
        if not stops:
            return (None, None)
            
        # Collect (zone_id, zone_version_id) pairs from all assigned stops
        zone_assignments = []
        for stop in stops:
            if not stop.order_id:
                continue
                
            # Query zone assignment for this order
            assignment = db.session.query(OrderZoneAssignment).filter_by(
                order_id=stop.order_id
            ).first()
            
            # Skip unassigned or None zones
            if assignment and assignment.zone_id and not assignment.is_unassigned:
                zone_assignments.append((assignment.zone_id, assignment.zone_version_id))
        
        if not zone_assignments:
            return (None, None)
            
        # Count zone frequencies
        zone_counts = Counter(zone_id for zone_id, _ in zone_assignments)
        total_stops_with_zones = len(zone_assignments)
        
        # Check for majority zone (>= 60% threshold)
        majority_threshold = 0.6
        for zone_id, count in zone_counts.most_common(1):
            ratio = count / total_stops_with_zones
            if ratio >= majority_threshold:
                # Find the zone_version_id for this majority zone
                for zid, zvid in zone_assignments:
                    if zid == zone_id:
                        logger.info(
                            f"Route {route_solution.id}: derived zone {zone_id} "
                            f"({count}/{total_stops_with_zones} stops, {ratio:.1%})"
                        )
                        return (zone_id, zvid)
        
        # No majority zone found
        logger.debug(
            f"Route {route_solution.id}: no majority zone "
            f"(threshold 60%, best: {zone_counts.most_common(1)[0] if zone_counts else 'none'})"
        )
        return (None, None)
        
    except Exception as e:
        logger.error(f"Error deriving route zone for route {route_solution.id}: {e}")
        return (None, None)
