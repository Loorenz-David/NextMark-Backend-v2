from datetime import datetime, timezone

from google.maps import routeoptimization_v1

from Delivery_app_BK.route_optimization.domain.models import OptimizationRequest
from Delivery_app_BK.route_optimization.providers.google.client import GoogleRouteOptimizationProvider


class _FakeOptimizeClient:
    def optimize_tours(self, request):
        return routeoptimization_v1.OptimizeToursResponse(
            routes=[
                {
                    "vehicle_label": "vehicle-120",
                    "vehicle_start_time": "2026-03-19T21:56:34Z",
                    "vehicle_end_time": "2026-03-20T00:11:01Z",
                    "visits": [
                        {
                            "shipment_label": "group:124:first",
                            "start_time": "2026-03-19T22:20:00Z",
                        }
                    ],
                    "transitions": [
                        {
                            "travel_distance_meters": 13158,
                            "travel_duration": "1406s",
                        }
                    ],
                }
            ]
        )


def _build_request() -> OptimizationRequest:
    return OptimizationRequest(
        route_plan_id=1,
        route_group_id=120,
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
        populate_transition_polylines=False,
    )


def test_google_provider_uses_preserved_proto_field_names(monkeypatch):
    monkeypatch.setattr(
        "Delivery_app_BK.route_optimization.providers.google.client.get_optimization_client",
        lambda: _FakeOptimizeClient(),
    )

    provider = GoogleRouteOptimizationProvider(project_id="test-project")
    result = provider.optimize(_build_request())

    assert result.total_distance_meters == 13158
    assert result.total_duration_seconds == 1406
    assert result.expected_start_time == datetime(2026, 3, 19, 21, 56, 34, tzinfo=timezone.utc)
    assert result.expected_end_time == datetime(2026, 3, 20, 0, 11, 1, tzinfo=timezone.utc)
    assert len(result.stops) == 1
    assert result.stops[0].expected_arrival_time == datetime(2026, 3, 19, 22, 20, 0, tzinfo=timezone.utc)
