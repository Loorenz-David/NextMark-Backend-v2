from __future__ import annotations

from typing import Protocol

from Delivery_app_BK.route_optimization.domain.models import OptimizationRequest, OptimizationResult


class RouteOptimizationProvider(Protocol):
    name: str

    def optimize(self, request: OptimizationRequest) -> OptimizationResult:
        ...
