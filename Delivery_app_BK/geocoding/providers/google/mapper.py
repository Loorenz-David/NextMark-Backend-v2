from __future__ import annotations

from typing import Any

from Delivery_app_BK.geocoding.domain.models import GeocodeResult


class GoogleGeocodingResponseMapper:
    """
    Maps a raw Google Geocoding REST API response dict to a GeocodeResult.

    Google response shape:
    {
      "status": "OK",
      "results": [{
        "formatted_address": "Kungsgatan 5, 111 56 Stockholm, Sweden",
        "geometry": { "location": { "lat": 59.334, "lng": 18.063 } },
        "address_components": [
          { "long_name": "5",          "short_name": "5",   "types": ["street_number"] },
          { "long_name": "Kungsgatan", "short_name": "...", "types": ["route"] },
          { "long_name": "Stockholm",  "short_name": "...", "types": ["postal_town"] },
          { "long_name": "Sweden",     "short_name": "SE",  "types": ["country", "political"] },
          { "long_name": "111 56",     "short_name": "...", "types": ["postal_code"] }
        ]
      }]
    }
    """

    @staticmethod
    def parse(response: dict[str, Any]) -> GeocodeResult | None:
        results = response.get("results") or []
        if not results:
            return None

        hit = results[0]
        components = hit.get("address_components") or []
        location = (hit.get("geometry") or {}).get("location") or {}
        formatted = hit.get("formatted_address", "")

        lat = location.get("lat")
        lng = location.get("lng")
        if lat is None or lng is None:
            return None

        def get_comp(type_: str, name_type: str = "long_name") -> str:
            for c in components:
                if type_ in (c.get("types") or []):
                    return c.get(name_type, "")
            return ""

        street_number = get_comp("street_number")
        route = get_comp("route")

        # Build street_address: route comes before number in most European locales
        if route and street_number:
            street_address = f"{route} {street_number}"
        elif route:
            street_address = route
        else:
            # Fall back to first segment of formatted_address
            street_address = formatted.split(",")[0].strip()

        # City: postal_town is specific (e.g. Stockholm city proper) vs locality (broader)
        city = get_comp("postal_town") or get_comp("locality") or get_comp("administrative_area_level_2")

        return GeocodeResult(
            street_address=street_address,
            postal_code=get_comp("postal_code"),
            city=city,
            country=get_comp("country", "short_name"),   # ISO alpha-2
            lat=float(lat),
            lng=float(lng),
            formatted_address=formatted,
        )
