from datetime import datetime, timezone

from Delivery_app_BK.route_optimization.domain.models import OptimizationRequest
from Delivery_app_BK.route_optimization.providers.google.mapper import GoogleResponseMapper


def _build_request(*, populate_transition_polylines: bool = False) -> OptimizationRequest:
    return OptimizationRequest(
        route_plan_id=1,
        route_group_id=124,
        route_solution_id=77,
        shipments=[],
        start_location={},
        end_location={},
        start_coordinates={"latitude": 59.0, "longitude": 18.0},
        end_coordinates={"latitude": 59.0, "longitude": 18.0},
        global_start_time=None,
        global_end_time=None,
        consider_traffic=False,
        route_modifiers={},
        objectives=[],
        travel_mode="DRIVE",
        cost_per_kilometer=1.0,
        populate_transition_polylines=populate_transition_polylines,
    )


def test_google_response_mapper_populates_totals_and_boundary_times_from_preserved_proto_fields():
    request = _build_request()
    response_dict = {
        "routes": [
            {
                "vehicle_start_time": "2026-03-19T21:56:34Z",
                "vehicle_end_time": "2026-03-20T00:11:01Z",
                "visits": [
                    {
                        "shipment_label": "group:124:first",
                        "start_time": "2026-03-19T22:20:00Z",
                    },
                    {
                        "shipment_label": "group:124:last",
                        "start_time": "2026-03-19T23:20:11Z",
                    },
                ],
                "transitions": [
                    {
                        "travel_distance_meters": 13158.0,
                        "travel_duration": "1406s",
                    },
                    {
                        "travel_distance_meters": 72217.0,
                        "travel_duration": "3611s",
                    },
                ],
            }
        ]
    }

    result = GoogleResponseMapper.parse_response(response_dict=response_dict, request=request)

    assert result.total_distance_meters == 85375
    assert result.total_duration_seconds == 5017
    assert result.expected_start_time == datetime(2026, 3, 19, 21, 56, 34, tzinfo=timezone.utc)
    assert result.expected_end_time == datetime(2026, 3, 20, 0, 11, 1, tzinfo=timezone.utc)
    assert len(result.stops) == 2
    assert result.stops[0].expected_arrival_time == datetime(2026, 3, 19, 22, 20, 0, tzinfo=timezone.utc)
    assert result.stops[1].expected_arrival_time == datetime(2026, 3, 19, 23, 20, 11, tzinfo=timezone.utc)


def test_google_response_mapper_falls_back_to_route_metrics_when_transitions_are_missing():
    request = _build_request()
    response_dict = {
        "routes": [
            {
                "vehicle_start_time": "2026-03-19T21:56:34Z",
                "vehicle_end_time": "2026-03-20T00:11:01Z",
                "visits": [],
                "transitions": [],
                "metrics": {
                    "travel_distance_meters": 148286.0,
                    "total_duration": "8067s",
                },
            }
        ]
    }

    result = GoogleResponseMapper.parse_response(response_dict=response_dict, request=request)

    assert result.total_distance_meters == 148286
    assert result.total_duration_seconds == 8067
    assert result.expected_start_time == datetime(2026, 3, 19, 21, 56, 34, tzinfo=timezone.utc)
    assert result.expected_end_time == datetime(2026, 3, 20, 0, 11, 1, tzinfo=timezone.utc)

