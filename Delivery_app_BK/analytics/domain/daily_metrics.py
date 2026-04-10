"""Domain dataclass representing aggregated daily metrics for a team."""
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class AnalyticsDailyFact:
    """Aggregated daily metrics (not the ORM model)."""

    team_id: int
    date: date

    # Order-level
    total_orders_created: int = 0
    total_orders_completed: int = 0
    total_orders_failed: int = 0
    scheduled_orders: int = 0
    unscheduled_orders: int = 0
    completion_rate: float = 0.0

    # Route-level
    total_routes: int = 0
    routes_completed: int = 0
    routes_active: int = 0
    avg_delay_seconds: float = 0.0
    late_routes_count: int = 0
    on_time_routes_count: int = 0
    total_distance_meters: float = 0.0
    total_travel_time_seconds: float = 0.0

    # Spatial — None = global row
    zone_id: Optional[int] = None
    zone_version_id: Optional[int] = None
