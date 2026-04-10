"""
Merge fresh vehicle warnings into an existing route_solution.route_warnings list.

Usage pattern
-------------
Call ``apply_vehicle_warnings_to_route_solution`` wherever route_warnings are
rebuilt.  The helper:

1. Strips any stale vehicle warnings from the current list.
2. Recomputes vehicle warnings via ``compute_vehicle_warnings``.
3. Merges the two sets and persists back to the route_solution instance.

This is the **only** place that writes vehicle warnings — do not inline the
logic at call-sites.
"""

from __future__ import annotations

import logging
from typing import List, Optional, TYPE_CHECKING

from Delivery_app_BK.models import db
from .compute_vehicle_warnings import compute_vehicle_warnings

if TYPE_CHECKING:
    from Delivery_app_BK.models.tables.infrastructure.vehicle import Vehicle
    from Delivery_app_BK.models import RouteSolution

logger = logging.getLogger(__name__)

# The full set of warning types owned by this module.
# Used to strip stale vehicle warnings before merging fresh ones.
VEHICLE_WARNING_TYPES = {
    "vehicle_max_volume_exceeded",
    "vehicle_max_weight_exceeded",
    "vehicle_max_distance_exceeded",
    "vehicle_max_duration_exceeded",
}


def apply_vehicle_warnings_to_route_solution(
    route_solution: "RouteSolution",
    vehicle: Optional["Vehicle"],
    orders: list = None,
    flush: bool = False,
) -> None:
    """
    Recompute vehicle warnings and merge them into ``route_solution.route_warnings``.

    - Removes any stale vehicle warnings from the existing list so old entries
      never accumulate.
    - Preserves all non-vehicle warnings (e.g. ``route_end_time_exceeded``).
    - Updates ``has_route_warnings`` accordingly.

    Parameters
    ----------
    route_solution:
        The ORM instance to update in-place.
    vehicle:
        The assigned Vehicle ORM instance, or ``None`` when no vehicle is
        assigned (all vehicle warnings are cleared in that case).
    orders:
        List of Order ORM instances for volume/weight checks.  Safe to omit
        if the Order model has no volume/weight fields yet.
    flush:
        When ``True``, calls ``db.session.flush()`` after updating the
        instance so callers that need the change visible in the same
        transaction can rely on it.
    """
    # Strip stale vehicle warnings from the existing list
    existing_warnings: List[dict] = list(route_solution.route_warnings or [])
    non_vehicle_warnings = [
        w for w in existing_warnings
        if w.get("type") not in VEHICLE_WARNING_TYPES
    ]

    # Compute fresh vehicle warnings
    fresh_vehicle_warnings = compute_vehicle_warnings(
        route_solution=route_solution,
        vehicle=vehicle,
        orders=orders or [],
    )

    # Merge and persist
    merged = non_vehicle_warnings + fresh_vehicle_warnings
    route_solution.route_warnings = merged if merged else None
    route_solution.has_route_warnings = bool(merged)

    logger.info(
        "apply_vehicle_warnings route_solution_id=%s vehicle_id=%s "
        "vehicle_warnings=%d total_warnings=%d",
        getattr(route_solution, "id", None),
        getattr(vehicle, "id", None),
        len(fresh_vehicle_warnings),
        len(merged),
    )

    if flush:
        db.session.flush()
