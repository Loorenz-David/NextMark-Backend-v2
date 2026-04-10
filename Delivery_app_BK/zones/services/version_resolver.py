"""Active zone version resolver for assignment operations."""

from typing import Optional
from Delivery_app_BK.models.tables.zones.zone_version import ZoneVersion


def get_active_zone_version(team_id: int, city_key: str) -> Optional[ZoneVersion]:
    """
    Resolve the active zone version for a specific (team_id, city_key) pair.
    
    The active version is unique per (team_id, city_key) and is enforced
    via a partial unique index on the zone_version table.
    
    Args:
        team_id: Team owning the zones
        city_key: Normalized city identifier (e.g., "new_york", "unknown_city")
        
    Returns:
        Active ZoneVersion record, or None if no active version exists for this city
        
    Raises:
        IntegrityError: Only if the partial unique index is violated (should not happen)
    """
    return ZoneVersion.query.filter(
        ZoneVersion.team_id == team_id,
        ZoneVersion.city_key == city_key,
        ZoneVersion.is_active == True,
    ).one_or_none()
