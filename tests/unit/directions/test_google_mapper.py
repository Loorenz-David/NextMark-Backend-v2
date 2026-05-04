from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from Delivery_app_BK.directions.domain.models import (
    DirectionsRequest,
    DirectionsStopInput,
)
from Delivery_app_BK.directions.providers.google.mapper import (
    GoogleDirectionsResponseMapper,
)


def _leg(duration_seconds: int, distance_meters: int):
    return SimpleNamespace(
        duration=f"{duration_seconds}s",
        distance_meters=distance_meters,
        polyline=SimpleNamespace(encoded_polyline=f"polyline-{duration_seconds}"),
    )


def test_parse_response_uses_sum_of_leg_durations_for_total_duration():
    departure_time = datetime(2026, 5, 4, 11, 53, 0, tzinfo=timezone.utc)
    request = DirectionsRequest(
        origin={"latitude": 59.413366, "longitude": 17.922466},
        destination={"latitude": 59.413366, "longitude": 17.922466},
        intermediates=[
            DirectionsStopInput(
                order_id=4456,
                location={"latitude": 59.245202, "longitude": 17.970879},
                service_duration_seconds=600,
            ),
            DirectionsStopInput(
                order_id=4458,
                location={"latitude": 59.320693, "longitude": 17.989013},
                service_duration_seconds=300,
            ),
        ],
        travel_mode="DRIVING",
        consider_traffic=True,
        route_modifiers={},
        departure_time=departure_time,
    )
    response = SimpleNamespace(
        routes=[
            SimpleNamespace(
                duration="9999s",
                distance_meters=57194,
                legs=[
                    _leg(1200, 10000),
                    _leg(900, 12000),
                    _leg(600, 8000),
                ],
            )
        ]
    )

    result = GoogleDirectionsResponseMapper.parse_response(response, request)

    assert result.total_duration_seconds == 2700
    assert result.total_distance_meters == 57194
    assert result.stop_results[0].arrival_time == datetime(
        2026, 5, 4, 12, 13, 0, tzinfo=timezone.utc
    )
    assert result.stop_results[1].arrival_time == datetime(
        2026, 5, 4, 12, 38, 0, tzinfo=timezone.utc
    )
    assert result.end_time == datetime(2026, 5, 4, 12, 53, 0, tzinfo=timezone.utc)


def test_parse_response_falls_back_to_route_duration_when_legs_are_missing():
    departure_time = datetime(2026, 5, 4, 11, 53, 0, tzinfo=timezone.utc)
    request = DirectionsRequest(
        origin={"latitude": 59.413366, "longitude": 17.922466},
        destination={"latitude": 59.245202, "longitude": 17.970879},
        intermediates=[],
        travel_mode="DRIVING",
        consider_traffic=True,
        route_modifiers={},
        departure_time=departure_time,
    )
    response = SimpleNamespace(
        routes=[
            SimpleNamespace(
                duration="1234s",
                distance_meters=10000,
                legs=[],
            )
        ]
    )

    result = GoogleDirectionsResponseMapper.parse_response(response, request)

    assert result.total_duration_seconds == 1234
