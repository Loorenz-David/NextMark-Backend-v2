"""
Compute vehicle capacity/distance/duration warnings for a route solution.

All vehicle warning computation is centralised here.  Call-sites must not
duplicate this logic — import and call ``compute_vehicle_warnings`` instead.

Note on volume/weight checks
-----------------------------
Order.total_volume_cm3 and Order.total_weight_g are denormalized columns
recomputed on every item mutation.  The checks use ``getattr`` so they
gracefully return 0 for any unbackfilled rows (i.e. orders created before
the backfill script was run).
"""

from __future__ import annotations

import logging
from typing import List, Optional, TYPE_CHECKING

from Delivery_app_BK.models.schemas.vehicle_warning_schema import build_vehicle_warning

if TYPE_CHECKING:
    from Delivery_app_BK.models.tables.infrastructure.vehicle import Vehicle
    from Delivery_app_BK.models import RouteSolution

logger = logging.getLogger(__name__)


def compute_vehicle_warnings(
    route_solution: "RouteSolution",
    vehicle: Optional["Vehicle"],
    orders: list = None,
) -> List[dict]:
    """
    Compute vehicle warnings for a route solution.

    Returns a list of warning dicts matching ``VEHICLE_WARNING_SCHEMA``.
    Any check whose limit field on the Vehicle is ``None`` is silently skipped.
    """
    if vehicle is None:
        return []

    warnings: List[dict] = []
    orders = orders or []

    # --- Volume check ---------------------------------------------------
    # Skipped when vehicle has no limit OR no order carries volume data.
    if vehicle.max_volume_load_cm3 is not None:
        total_volume = sum(
            getattr(order, "total_volume_cm3", None) or 0
            for order in orders
        )
        if total_volume > vehicle.max_volume_load_cm3:
            warnings.append(build_vehicle_warning(
                warning_type="vehicle_max_volume_exceeded",
                actual_value=total_volume,
                limit_value=vehicle.max_volume_load_cm3,
                message=(
                    f"Route volume {total_volume:,} cm³ exceeds vehicle limit "
                    f"{vehicle.max_volume_load_cm3:,} cm³."
                ),
            ))
            logger.debug(
                "vehicle_max_volume_exceeded route_solution_id=%s actual=%s limit=%s",
                getattr(route_solution, "id", None),
                total_volume,
                vehicle.max_volume_load_cm3,
            )

    # --- Weight check ---------------------------------------------------
    if vehicle.max_weight_load_g is not None:
        total_weight = sum(
            getattr(order, "total_weight_g", None) or 0
            for order in orders
        )
        if total_weight > vehicle.max_weight_load_g:
            warnings.append(build_vehicle_warning(
                warning_type="vehicle_max_weight_exceeded",
                actual_value=total_weight,
                limit_value=vehicle.max_weight_load_g,
                message=(
                    f"Route weight {total_weight:,} g exceeds vehicle limit "
                    f"{vehicle.max_weight_load_g:,} g."
                ),
            ))
            logger.debug(
                "vehicle_max_weight_exceeded route_solution_id=%s actual=%s limit=%s",
                getattr(route_solution, "id", None),
                total_weight,
                vehicle.max_weight_load_g,
            )

    # --- Distance check -------------------------------------------------
    if (
        vehicle.travel_distance_limit_km is not None
        and route_solution.total_distance_meters is not None
    ):
        total_km = route_solution.total_distance_meters / 1000
        limit_km = float(vehicle.travel_distance_limit_km)
        if total_km > limit_km:
            warnings.append(build_vehicle_warning(
                warning_type="vehicle_max_distance_exceeded",
                actual_value=round(total_km, 2),
                limit_value=limit_km,
                message=(
                    f"Route distance {total_km:.1f} km exceeds vehicle limit "
                    f"{limit_km:.1f} km."
                ),
            ))
            logger.debug(
                "vehicle_max_distance_exceeded route_solution_id=%s actual_km=%.2f limit_km=%.2f",
                getattr(route_solution, "id", None),
                total_km,
                limit_km,
            )

    # --- Duration check -------------------------------------------------
    if (
        vehicle.travel_duration_limit_minutes is not None
        and route_solution.total_travel_time_seconds is not None
    ):
        total_minutes = route_solution.total_travel_time_seconds / 60
        limit_minutes = float(vehicle.travel_duration_limit_minutes)
        if total_minutes > limit_minutes:
            warnings.append(build_vehicle_warning(
                warning_type="vehicle_max_duration_exceeded",
                actual_value=round(total_minutes, 1),
                limit_value=limit_minutes,
                message=(
                    f"Route duration {total_minutes:.0f} min exceeds vehicle limit "
                    f"{limit_minutes:.0f} min."
                ),
            ))
            logger.debug(
                "vehicle_max_duration_exceeded route_solution_id=%s actual_min=%.1f limit_min=%.1f",
                getattr(route_solution, "id", None),
                total_minutes,
                limit_minutes,
            )

    return warnings
