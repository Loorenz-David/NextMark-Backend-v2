from __future__ import annotations

from typing import Protocol

from Delivery_app_BK.directions.domain.models import DirectionsRequest, DirectionsResult


class DirectionsProvider(Protocol):
    name: str

    def compute(self, request: DirectionsRequest) -> DirectionsResult:
        ...
