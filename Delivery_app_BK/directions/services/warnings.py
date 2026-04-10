from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from Delivery_app_BK.models import Order, RouteSolution
from Delivery_app_BK.directions.services.time_window_policy import (
    build_stop_time_warnings as _build_stop_time_warnings,
    ensure_utc,
)

__all__ = ["build_stop_time_warnings", "ensure_utc"]


def build_stop_time_warnings(
    order: Optional[Order],
    arrival_time: Optional[datetime],
    route_solution: RouteSolution,
) -> List[dict]:
    return _build_stop_time_warnings(order, arrival_time, route_solution)
