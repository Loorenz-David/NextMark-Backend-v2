from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from Delivery_app_BK.services.context import ServiceContext
    from Delivery_app_BK.models import RoutePlan
    from Delivery_app_BK.models import (
        RouteGroup,
    )
    from Delivery_app_BK.models.tables.order.order import Order
    from Delivery_app_BK.models import (
        RouteSolution,
    )
    from Delivery_app_BK.models.tables.infrastructure.vehicle import Vehicle
from Delivery_app_BK.route_optimization.constants.route_end_strategy import ROUND_TRIP, CUSTOM_END_ADDRESS


@dataclass(frozen=True)
class TimeWindow:
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


@dataclass(frozen=True)
class ShipmentMember:
    order_id: int
    service_duration_seconds: int = 0


@dataclass(frozen=True)
class Shipment:
    label: str
    location: Dict[str, float]
    members: List[ShipmentMember] = field(default_factory=list)
    time_windows: List[TimeWindow] = field(default_factory=list)
    service_duration_seconds: Optional[int] = None


@dataclass(frozen=True)
class OptimizationRequest:
    route_plan_id: int
    route_group_id: int
    route_solution_id: int
    shipments: List[Shipment]
    start_location: Dict[str, Any]
    end_location: Dict[str, Any]
    start_coordinates: Dict[str, float]
    end_coordinates: Dict[str, float]
    global_start_time: Optional[datetime]
    global_end_time: Optional[datetime]
    consider_traffic: bool
    route_modifiers: Dict[str, bool]
    objectives: List[Dict[str, Any]]
    travel_mode: str
    cost_per_kilometer: float
    pre_skipped_shipments: List["SkippedShipment"] = field(default_factory=list)
    excluded_shipments: List[Shipment] = field(default_factory=list)
    populate_transition_polylines: bool = True
    injected_routes: Optional[List[Dict[str, Any]]] = None
    interpret_injected_solutions_using_labels: bool = False

@dataclass(frozen=True)
class StopResult:
    shipment_label: str
    stop_order: int
    expected_arrival_time: Optional[datetime]
    in_range: bool


@dataclass(frozen=True)
class SkippedShipment:
    shipment_label: str
    reason: Optional[str] = None


@dataclass(frozen=True)
class OptimizationResult:
    total_distance_meters: int
    total_duration_seconds: int
    expected_start_time: Optional[datetime]
    expected_end_time: Optional[datetime]
    stops: List[StopResult]
    skipped: List[SkippedShipment]
    transition_polylines: Optional[List[Optional[str]]] = None


@dataclass(frozen=True)
class OptimizationContext:
    route_group: "RouteGroup"
    route_plan: "RoutePlan"
    route_solution: "RouteSolution"
    orders: List["Order"]
    identity: Dict[str, Any] = field(default_factory=dict)
    incoming_data: Dict[str, Any] = field(default_factory=dict)
    interpret_injected_solutions_using_labels: bool = True
    return_shape: str = "map_ids_object"
    route_end_strategy: str = ROUND_TRIP
    ctx: "ServiceContext | None" = None
    vehicle: "Vehicle | None" = None
