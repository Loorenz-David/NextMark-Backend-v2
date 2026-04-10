from __future__ import annotations

from Delivery_app_BK.geocoding.domain.models import GeocodeRequest, GeocodeResult
from Delivery_app_BK.geocoding.providers.base import GeocodingProvider
from Delivery_app_BK.geocoding.providers.google import GoogleGeocodingProvider


def geocode_address(
    query: str,
    *,
    country_hint: str | None = None,
    provider: GeocodingProvider | None = None,
) -> GeocodeResult | None:
    """
    Resolve a free-text address string to a structured GeocodeResult.

    Args:
        query:        Free-text address query (e.g. "Kungsgatan 5, Stockholm").
        country_hint: ISO 3166-1 alpha-2 country code to narrow results (e.g. "SE").
                      Does not restrict — it biases the search toward that country.
        provider:     Optional provider override. Defaults to GoogleGeocodingProvider.
                      Inject a stub here in tests or to swap to a different API.

    Returns:
        GeocodeResult with coordinates, or None if no match is found.
    """
    resolved_provider = provider or GoogleGeocodingProvider()
    request = GeocodeRequest(query=query, country_hint=country_hint)
    return resolved_provider.geocode(request)
