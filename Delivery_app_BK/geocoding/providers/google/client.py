from __future__ import annotations

import logging

import requests

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.geocoding.domain.models import GeocodeRequest, GeocodeResult
from Delivery_app_BK.geocoding.providers.base import GeocodingProvider
from Delivery_app_BK.geocoding.providers.google.mapper import GoogleGeocodingResponseMapper
from Delivery_app_BK.lib.google_credentials import get_google_geocoding_api_key

logger = logging.getLogger(__name__)

_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
_TIMEOUT_SECONDS = 5


class GoogleGeocodingProvider:
    """
    Geocoding provider backed by the Google Geocoding REST API.

    Authentication source follows the same pattern as the directions provider:
    1. GOOGLE_GEOCODING_API_KEY environment variable (local development)
    2. AWS Secrets Manager secret (production)

    This API key is separate from the service-account credentials used by the Routes API.

    To swap this provider, implement GeocodingProvider Protocol and pass it anywhere
    a GeocodingProvider is accepted (e.g. geocoding orchestrator or tests).
    """

    name = "google_geocoding"

    def __init__(self, api_key: str | None = None) -> None:
        try:
            key = api_key or get_google_geocoding_api_key()
        except RuntimeError as exc:
            raise ValidationFailed(
                "Google geocoding credentials are not configured. "
                "Set GOOGLE_GEOCODING_API_KEY locally or configure the AWS secret."
            ) from exc
        self._api_key = key

    def geocode(self, request: GeocodeRequest) -> GeocodeResult | None:
        params: dict = {
            "address": request.query,
            "key": self._api_key,
        }
        if request.country_hint:
            params["components"] = f"country:{request.country_hint}"

        logger.debug("Google geocode request | query=%r | country_hint=%r", request.query, request.country_hint)

        try:
            response = requests.get(_GEOCODE_URL, params=params, timeout=_TIMEOUT_SECONDS)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ValidationFailed(f"Google Geocoding API request failed: {exc}") from exc

        data = response.json()
        status = data.get("status")

        if status == "REQUEST_DENIED":
            raise ValidationFailed(
                f"Google Geocoding API denied the request: {data.get('error_message', 'check your API key')}"
            )

        if status not in ("OK", "ZERO_RESULTS"):
            logger.warning("Google geocode unexpected status | status=%s | query=%r", status, request.query)

        result = GoogleGeocodingResponseMapper.parse(data)

        logger.info(
            "Google geocode result | query=%r | found=%s | formatted=%r",
            request.query,
            result is not None,
            result.formatted_address if result else None,
        )
        return result
