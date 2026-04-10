from __future__ import annotations

from typing import Protocol

from Delivery_app_BK.geocoding.domain.models import GeocodeRequest, GeocodeResult


class GeocodingProvider(Protocol):
    name: str

    def geocode(self, request: GeocodeRequest) -> GeocodeResult | None:
        """
        Resolve a query string to a structured address with coordinates.
        Returns None if no result is found.
        """
        ...
