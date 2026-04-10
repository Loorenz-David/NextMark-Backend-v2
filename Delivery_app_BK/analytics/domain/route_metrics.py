"""Domain dataclass representing computed metrics for a single RouteSolution."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class RouteMetricsSnapshot:
    """Computed per-route metric snapshot (not the ORM model)."""

    route_solution_id: int
    team_id: int
    expected_start_time: Optional[datetime]

    total_stops: int = 0
    on_time_stops: int = 0
    early_stops: int = 0
    late_stops: int = 0
    avg_delay_seconds: float = 0.0
    max_delay_seconds: float = 0.0
    on_time_rate: float = 0.0
    delay_rate: float = 0.0

    total_distance_meters: float = 0.0
    total_travel_time_seconds: float = 0.0
    total_service_time_seconds: float = 0.0
    total_orders: int = 0

    # Spatial — populated once Phase 4 delivers zone attribution
    zone_id: Optional[int] = None
    zone_version_id: Optional[int] = None

    computed_at: Optional[datetime] = field(default=None)
