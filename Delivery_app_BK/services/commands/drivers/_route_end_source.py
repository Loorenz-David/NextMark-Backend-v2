from __future__ import annotations

from Delivery_app_BK.models import RouteSolution
from Delivery_app_BK.services.domain.route_operations.route_solution import RouteActualEndTimeSource

ROUTE_END_SOURCE_EXPECTED = RouteActualEndTimeSource.EXPECTED.value
ROUTE_END_SOURCE_LAST_ORDER = RouteActualEndTimeSource.LAST_ORDER_PROJECTION.value
ROUTE_END_SOURCE_MANUAL = RouteActualEndTimeSource.MANUAL_COMPLETION.value


def get_driver_actual_end_time_source(route_solution: RouteSolution) -> str | None:
    source = getattr(route_solution, "actual_end_time_source", None)
    if isinstance(source, RouteActualEndTimeSource):
        return source.value
    if not isinstance(source, str):
        return None
    try:
        return RouteActualEndTimeSource(source).value
    except ValueError:
        return None


def set_driver_actual_end_time_source(route_solution: RouteSolution, source: str | None) -> None:
    route_solution.actual_end_time_source = source
