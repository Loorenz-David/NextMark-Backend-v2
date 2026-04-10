"""
Vehicle Selection Domain

Encapsulates all logic for choosing which vehicle should be assigned to a route solution.
This is the single source of truth for vehicle eligibility rules and preference ranking.

Rules (in priority order):
1. Vehicle must be active (is_active=True)
2. Vehicle must have ALL required capabilities (if specified)
3. Vehicle must not be in excluded list (already assigned in this plan)
4. Preferred vehicle IDs are tried first, then general pool

This module is designed to be extended as vehicle selection becomes more sophisticated.
"""

from typing import TYPE_CHECKING, Optional

from Delivery_app_BK.errors import ValidationFailed

if TYPE_CHECKING:
    from Delivery_app_BK.models.tables.infrastructure.vehicle import Vehicle


def select_vehicle_for_route_solution(
    team_id: int,
    preferred_vehicle_ids: Optional[list[int]] = None,
    required_capabilities: Optional[list[str]] = None,
    excluded_vehicle_ids: Optional[set[int]] = None,
) -> Optional[int]:
    """
    Select a vehicle to assign to a route solution.

    Decision logic:
    1. Filter by activation and capability requirements
    2. If preferred_vehicle_ids provided, pick first available from that list
    3. Otherwise, pick first available from general pool

    Args:
        team_id: Team ID (required for team-scoping)
        preferred_vehicle_ids: Ordered list of vehicle IDs to try first. Can be None or empty.
        required_capabilities: All vehicles must have these capabilities. Can be None or empty.
        excluded_vehicle_ids: Set of vehicle IDs to skip (already assigned). Defaults to empty set.

    Returns:
        Vehicle ID if a suitable vehicle found, None otherwise.

    Raises:
        ValidationFailed: If required_capabilities contains invalid values.
    """
    # Import here to avoid circular imports
    from Delivery_app_BK.models.tables.infrastructure.vehicle import Vehicle
    
    if excluded_vehicle_ids is None:
        excluded_vehicle_ids = set()

    # Build base query: active vehicles for this team
    query = Vehicle.query.filter(
        Vehicle.team_id == team_id,
        Vehicle.is_active.is_(True),
    )

    # Filter by required capabilities if specified
    if required_capabilities:
        _validate_capability_list(required_capabilities)
        query = _filter_by_required_capabilities(query, required_capabilities)

    # Get all eligible vehicles, excluding those already assigned
    eligible_vehicles = query.all()
    eligible_ids = [v.id for v in eligible_vehicles if v.id not in excluded_vehicle_ids]

    if not eligible_ids:
        return None

    # If preferred list provided, try those first
    if preferred_vehicle_ids:
        for vehicle_id in preferred_vehicle_ids:
            if vehicle_id in eligible_ids:
                return vehicle_id

    # Fall back to first available from general pool
    return eligible_ids[0] if eligible_ids else None


def _validate_capability_list(capabilities: list[str]) -> None:
    """Validate that all items in capability list are valid enum values."""
    from Delivery_app_BK.services.domain.vehicle.capabilities import VALID_VEHICLE_CAPABILITIES

    if not isinstance(capabilities, list):
        raise ValidationFailed("required_capabilities must be a list")

    for idx, cap in enumerate(capabilities):
        if not isinstance(cap, str):
            raise ValidationFailed(f"required_capabilities[{idx}] must be a string")

        cap_normalized = cap.strip().lower()
        if cap_normalized not in VALID_VEHICLE_CAPABILITIES:
            raise ValidationFailed(
                f"Invalid capability '{cap}'. "
                f"Must be one of: {', '.join(sorted(VALID_VEHICLE_CAPABILITIES))}"
            )


def _filter_by_required_capabilities(query, required_capabilities: list[str]):
    """
    Filter query to only vehicles that have ALL required capabilities.

    PostgreSQL JSONB 'contains' logic:
    - capabilities @> '["cold_chain", "fragile"]'::jsonb
    means: capabilities array includes both cold_chain AND fragile
    """
    from sqlalchemy import and_

    # Import here to avoid circular imports
    from Delivery_app_BK.models.tables.infrastructure.vehicle import Vehicle

    # Build the contains condition for each capability
    conditions = [
        Vehicle.capabilities.contains([cap]) for cap in required_capabilities
    ]

    return query.filter(and_(*conditions))
