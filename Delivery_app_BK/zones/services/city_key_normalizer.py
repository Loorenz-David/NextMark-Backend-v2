"""City key normalization utility for zone scoping."""

import re
from typing import Optional


def normalize_city_key(city: Optional[str]) -> str:
    """
    Normalize a city name to a canonical city key for zone scoping.
    
    City keys are:
    - Lowercase
    - Trimmed of whitespace
    - With special characters removed (A-Z, a-z, 0-9, underscore only)
    - Default to "unknown_city" if empty or None
    
    Args:
        city: Raw city name from address, or None
        
    Returns:
        Normalized city key suitable for zone queries
        
    Example:
        >>> normalize_city_key("New York")
        "new_york"
        >>> normalize_city_key("São Paulo")
        "so_paulo"
        >>> normalize_city_key(None)
        "unknown_city"
    """
    if not city:
        return "unknown_city"
    
    # Trim and lowercase
    normalized = city.strip().lower()
    
    # Return "unknown_city" if empty after trim
    if not normalized:
        return "unknown_city"
    
    # Remove special characters: keep only alphanumeric and spaces/underscores
    # Replace spaces with underscores
    normalized = re.sub(r'[^a-z0-9\s]', '', normalized)
    normalized = re.sub(r'\s+', '_', normalized)
    
    # Remove consecutive underscores
    normalized = re.sub(r'_+', '_', normalized)
    
    # Strip leading/trailing underscores
    normalized = normalized.strip('_')
    
    # Return "unknown_city" if nothing left
    return normalized if normalized else "unknown_city"
