"""
Unit tests for the Google Geocoding response mapper.
No HTTP calls — pure parsing of synthetic response dicts.
"""
from Delivery_app_BK.geocoding.providers.google.mapper import GoogleGeocodingResponseMapper


def _build_response(
    *,
    street_number: str = "5",
    route: str = "Kungsgatan",
    postal_town: str = "Stockholm",
    country_long: str = "Sweden",
    country_short: str = "SE",
    postal_code: str = "111 56",
    lat: float = 59.334,
    lng: float = 18.063,
    formatted: str = "Kungsgatan 5, 111 56 Stockholm, Sweden",
) -> dict:
    return {
        "status": "OK",
        "results": [
            {
                "formatted_address": formatted,
                "geometry": {"location": {"lat": lat, "lng": lng}},
                "address_components": [
                    {"long_name": street_number, "short_name": street_number, "types": ["street_number"]},
                    {"long_name": route, "short_name": route, "types": ["route"]},
                    {"long_name": postal_town, "short_name": postal_town, "types": ["postal_town"]},
                    {"long_name": country_long, "short_name": country_short, "types": ["country", "political"]},
                    {"long_name": postal_code, "short_name": postal_code, "types": ["postal_code"]},
                ],
            }
        ],
    }


def test_mapper_extracts_all_fields():
    result = GoogleGeocodingResponseMapper.parse(_build_response())

    assert result is not None
    assert result.street_address == "Kungsgatan 5"
    assert result.postal_code == "111 56"
    assert result.city == "Stockholm"
    assert result.country == "SE"
    assert result.lat == 59.334
    assert result.lng == 18.063
    assert "Stockholm" in result.formatted_address


def test_mapper_returns_none_for_empty_results():
    result = GoogleGeocodingResponseMapper.parse({"status": "ZERO_RESULTS", "results": []})
    assert result is None


def test_mapper_returns_none_when_coordinates_missing():
    response = {
        "status": "OK",
        "results": [
            {
                "formatted_address": "Some Street",
                "geometry": {"location": {}},  # missing lat/lng
                "address_components": [],
            }
        ],
    }
    result = GoogleGeocodingResponseMapper.parse(response)
    assert result is None


def test_mapper_falls_back_to_formatted_address_for_street_when_no_route():
    response = {
        "status": "OK",
        "results": [
            {
                "formatted_address": "Stockholm Central, Stockholm",
                "geometry": {"location": {"lat": 59.33, "lng": 18.06}},
                "address_components": [
                    {"long_name": "Stockholm", "short_name": "Stockholm", "types": ["postal_town"]},
                    {"long_name": "Sweden", "short_name": "SE", "types": ["country", "political"]},
                ],
            }
        ],
    }
    result = GoogleGeocodingResponseMapper.parse(response)
    assert result is not None
    # Falls back to first segment of formatted_address
    assert result.street_address == "Stockholm Central"
    assert result.country == "SE"


def test_to_address_dict_matches_address_schema():
    result = GoogleGeocodingResponseMapper.parse(_build_response())
    addr = result.to_address_dict()

    assert set(addr.keys()) == {"street_address", "postal_code", "city", "country", "coordinates"}
    assert set(addr["coordinates"].keys()) == {"lat", "lng"}
    assert isinstance(addr["coordinates"]["lat"], float)
    assert isinstance(addr["coordinates"]["lng"], float)
