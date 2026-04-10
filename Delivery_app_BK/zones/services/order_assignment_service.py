"""Order zone assignment service for persisting zone assignments."""

from typing import Optional, Tuple
from Delivery_app_BK.models import db
from Delivery_app_BK.models.tables.zones.order_zone_assignment import OrderZoneAssignment
from .city_key_normalizer import normalize_city_key
from .version_resolver import get_active_zone_version
from .point_to_zone_resolver import resolve_point_to_zone


def upsert_order_zone_assignment(
    order_id: int,
    team_id: int,
    city_key: Optional[str] = None,
    client_address: Optional[dict] = None,
    user_specified_zone_id: Optional[int] = None,
) -> Tuple[OrderZoneAssignment, str]:
    """
    Upsert an order's zone assignment with priority semantics.
    
    Priority:
    1. User-specified (manual override)
    2. System-derived (from coordinates if available)
    3. Bootstrap (city-wide default) — not yet implemented, returns unassigned
    
    Args:
        order_id: Order being assigned
        team_id: Order's team
        city_key: Optional pre-normalized city key. If None, extracted and normalized from client_address
        client_address: JSONB address object with coordinates (lat, lng) and city
        user_specified_zone_id: If provided, creates manual override assignment
        
    Returns:
        Tuple of (OrderZoneAssignment instance, action taken)
        action = "manual_assigned" | "system_assigned" | "unassigned" | "no_change"
        
    Raises:
        ValueError: If coordinates are invalid or city cannot be determined
    """
    # Normalize city key if not provided
    if not city_key and client_address:
        city_key = normalize_city_key(client_address.get('city'))
    elif not city_key:
        city_key = normalize_city_key(None)
    
    # Validate coordinates if present
    coordinates = None
    if client_address and 'coordinates' in client_address:
        coords = client_address['coordinates']
        if coords and isinstance(coords, dict):
            lat = coords.get('lat')
            lng = coords.get('lng')
            if lat is not None and lng is not None:
                try:
                    coordinates = (float(lat), float(lng))
                except (ValueError, TypeError):
                    pass
    
    # Get active zone version for this city
    zone_version = get_active_zone_version(team_id, city_key)
    if not zone_version:
        # No active version yet for this city — unassigned
        return _create_unassigned_assignment(
            order_id,
            team_id,
            city_key,
            None,
            "no_candidate_zone",
        ), "unassigned"
    
    # Check for existing assignment
    existing = OrderZoneAssignment.query.filter_by(
        order_id=order_id,
    ).one_or_none()
    
    # Priority 1: User-specified (manual override)
    if user_specified_zone_id is not None:
        zone_id = user_specified_zone_id
        assignment_type = "manual"
        assignment_method = "manual_override"
        is_unassigned = False
        unassigned_reason = None
        
        if existing and existing.zone_id == zone_id and existing.assignment_type == assignment_type:
            return existing, "no_change"
        
        assignment = _upsert_assignment(
            order_id=order_id,
            team_id=team_id,
            city_key=city_key,
            zone_version_id=zone_version.id,
            zone_id=zone_id,
            assignment_type=assignment_type,
            assignment_method=assignment_method,
            is_unassigned=is_unassigned,
            unassigned_reason=unassigned_reason,
        )
        return assignment, "manual_assigned"
    
    # Priority 2: System-derived (from coordinates)
    if coordinates:
        lat, lng = coordinates
        resolution = resolve_point_to_zone(
            zone_version_id=zone_version.id,
            lat=lat,
            lng=lng,
            priority_types=["user", "system", "bootstrap"],
        )

        if resolution.zone:
            assignment_type = "auto"
            assignment_method = resolution.method

            if existing and existing.zone_id == resolution.zone.id and existing.assignment_type == assignment_type:
                return existing, "no_change"

            assignment = _upsert_assignment(
                order_id=order_id,
                team_id=team_id,
                city_key=city_key,
                zone_version_id=zone_version.id,
                zone_id=resolution.zone.id,
                assignment_type=assignment_type,
                assignment_method=assignment_method,
                is_unassigned=False,
                unassigned_reason=None,
            )
            return assignment, "system_assigned"
        else:
            return _create_unassigned_assignment(
                order_id,
                team_id,
                city_key,
                zone_version.id,
                resolution.unassigned_reason or "no_candidate_zone",
            ), "unassigned"
    
    # No coordinates available
    return _create_unassigned_assignment(
        order_id,
        team_id,
        city_key,
        zone_version.id,
        "no_coordinates",
    ), "unassigned"


def _upsert_assignment(
    order_id: int,
    team_id: int,
    city_key: str,
    zone_version_id: int,
    zone_id: int,
    assignment_type: str,
    assignment_method: Optional[str],
    is_unassigned: bool,
    unassigned_reason: Optional[str],
) -> OrderZoneAssignment:
    """Internal helper to upsert an assignment row."""
    assignment = OrderZoneAssignment.query.filter_by(order_id=order_id).one_or_none()
    
    if assignment:
        # Update existing
        assignment.team_id = team_id
        assignment.city_key = city_key
        assignment.zone_version_id = zone_version_id
        assignment.zone_id = zone_id
        assignment.assignment_type = assignment_type
        assignment.assignment_method = assignment_method
        assignment.is_unassigned = is_unassigned
        assignment.unassigned_reason = unassigned_reason
    else:
        # Create new
        assignment = OrderZoneAssignment(
            order_id=order_id,
            team_id=team_id,
            city_key=city_key,
            zone_version_id=zone_version_id,
            zone_id=zone_id,
            assignment_type=assignment_type,
            assignment_method=assignment_method,
            is_unassigned=is_unassigned,
            unassigned_reason=unassigned_reason,
        )
        db.session.add(assignment)
    
    db.session.commit()
    return assignment


def _create_unassigned_assignment(
    order_id: int,
    team_id: int,
    city_key: str,
    zone_version_id: Optional[int],
    unassigned_reason: str,
) -> OrderZoneAssignment:
    """Internal helper to create an unassigned assignment record."""
    return _upsert_assignment(
        order_id=order_id,
        team_id=team_id,
        city_key=city_key,
        zone_version_id=zone_version_id,
        zone_id=None,
        assignment_type="auto",
        assignment_method=None,
        is_unassigned=True,
        unassigned_reason=unassigned_reason,
    )
