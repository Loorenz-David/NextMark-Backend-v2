from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GeocodeRequest:
    """Input to the geocoding service."""

    query: str
    # ISO 3166-1 alpha-2 country code — narrows results but does not restrict them.
    # Example: "SE", "US", "DE"
    country_hint: str | None = None


@dataclass(frozen=True)
class GeocodeResult:
    """
    Resolved address, shaped to match ADDRESS_SCHEMA (address_schema.py).

    Fields map directly to the client_address dict expected by create_order:
      {
        "street_address": "Kungsgatan 5",
        "postal_code": "111 56",
        "city": "Stockholm",
        "country": "SE",
        "coordinates": { "lat": 59.3345, "lng": 18.0632 }
      }
    """

    street_address: str
    postal_code: str
    city: str
    country: str        # ISO 3166-1 alpha-2 short name  (e.g. "SE")
    lat: float
    lng: float
    formatted_address: str  # full human-readable string from provider (for logging)

    def to_address_dict(self) -> dict:
        """Return the dict that can be passed directly as client_address."""
        return {
            "street_address": self.street_address,
            "postal_code": self.postal_code,
            "city": self.city,
            "country": self.country,
            "coordinates": {"lat": self.lat, "lng": self.lng},
        }
