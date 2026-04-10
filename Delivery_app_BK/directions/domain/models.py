from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class DirectionsStopInput:
    order_id: int
    location: Dict[str, float]
    service_duration_seconds: Optional[int] = None


@dataclass(frozen=True)
class DirectionsVisitStopMember:
    stop_id: Optional[int]
    order_id: int
    service_duration_seconds: int = 0


@dataclass(frozen=True)
class DirectionsVisitGroup:
    location: Dict[str, float]
    location_key: str
    members: List[DirectionsVisitStopMember] = field(default_factory=list)


@dataclass(frozen=True)
class DirectionsRequest:
    origin: Dict[str, float]
    destination: Dict[str, float]
    intermediates: List[DirectionsStopInput]
    travel_mode: str
    consider_traffic: bool
    route_modifiers: Dict[str, bool]
    departure_time: Optional[datetime] = None


@dataclass(frozen=True)
class DirectionsStopResult:
    order_id: int
    arrival_time: Optional[datetime]
    travel_duration_seconds: int
    distance_meters: int


@dataclass(frozen=True)
class DirectionsResult:
    total_distance_meters: int
    total_duration_seconds: int
    leg_polylines: List[Optional[str]]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    stop_results: List[DirectionsStopResult] = field(default_factory=list)


@dataclass(frozen=True)
class DirectionsRequestBuildResult:
    request: DirectionsRequest
    full_recompute: bool
    effective_start_position: int
    anchor_order_id: Optional[int] = None
    affected_order_ids: List[int] = field(default_factory=list)
    visit_groups: List[DirectionsVisitGroup] = field(default_factory=list)
