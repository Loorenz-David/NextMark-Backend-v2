from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from Delivery_app_BK.route_optimization.domain.models import (
    OptimizationRequest,
    OptimizationResult,
    Shipment,
    ShipmentMember,
    SkippedShipment,
    StopResult,
)
from Delivery_app_BK.route_optimization.providers.google.mapper import (
    GoogleRequestMapper,
    GoogleResponseMapper,
)
from Delivery_app_BK.route_optimization.services import persister as persister_module
from Delivery_app_BK.route_optimization.services.request_builder import build_request


def _make_order(
    order_id: int,
    *,
    lat: float,
    lng: float,
    delivery_windows=None,
):
    return SimpleNamespace(
        id=order_id,
        client_address={
            "street_address": f"{order_id} Main St",
            "country": "Sweden",
            "coordinates": {"lat": lat, "lng": lng},
        },
        items=[],
        delivery_windows=list(delivery_windows or []),
    )


def _make_route_stop(stop_id: int, order_id: int, stop_order: int):
    return SimpleNamespace(
        id=stop_id,
        client_id=f"route_stop_{stop_id}",
        order_id=order_id,
        stop_order=stop_order,
        eta_status="valid",
        service_time=None,
        expected_arrival_time=None,
        expected_departure_time=None,
        expected_service_duration_seconds=None,
        in_range=None,
        reason_was_skipped=None,
        has_constraint_violation=False,
        constraint_warnings=None,
        to_next_polyline=None,
    )


def _make_context(*, with_existing_stops: bool) -> SimpleNamespace:
    order_1 = _make_order(order_id=101, lat=57.7, lng=11.97)
    order_2 = _make_order(
        order_id=102,
        lat=57.7000001,
        lng=11.9700001,
        delivery_windows=[
            SimpleNamespace(
                start_at=datetime(2026, 3, 8, 9, 0, tzinfo=timezone.utc),
                end_at=datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc),
            )
        ],
    )
    order_3 = _make_order(
        order_id=103,
        lat=57.71,
        lng=11.98,
        delivery_windows=[
            SimpleNamespace(
                start_at=datetime(2026, 3, 8, 8, 30, tzinfo=timezone.utc),
                end_at=datetime(2026, 3, 8, 9, 30, tzinfo=timezone.utc),
            )
        ],
    )

    route_stops = []
    if with_existing_stops:
        route_stops = [
            _make_route_stop(201, 101, 1),
            _make_route_stop(202, 102, 2),
            _make_route_stop(203, 103, 3),
        ]

    route_plan = SimpleNamespace(
        id=10,
        start_date=datetime(2026, 3, 8, 8, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 3, 8, 18, 0, tzinfo=timezone.utc),
    )
    route_group = SimpleNamespace(id=20, team_id=3, route_plan=route_plan)
    route_solution = SimpleNamespace(
        id=30,
        client_id="route_solution_30",
        label="Route 30",
        is_selected=False,
        stops=route_stops,
        start_location={
            "street_address": "Depot Street 1",
            "country": "Sweden",
            "coordinates": {"lat": 57.69, "lng": 11.96},
        },
        end_location=None,
        stops_service_time={"time": 5, "per_item": 0},
        set_start_time=None,
        set_end_time=None,
        start_leg_polyline=None,
        end_leg_polyline=None,
        total_distance_meters=None,
        total_travel_time_seconds=None,
        expected_start_time=None,
        expected_end_time=None,
        score=None,
        algorithm=None,
        is_optimized=None,
        has_route_warnings=False,
        route_warnings=None,
        stop_count=0,
        driver_id=None,
        route_group_id=20,
        route_group=route_group,
        start_location_id=None,
    )
    return SimpleNamespace(
        route_plan=route_plan,
        route_group=route_group,
        route_solution=route_solution,
        orders=[order_1, order_2, order_3],
        identity={},
        incoming_data={"populate_transition_polylines": True},
        interpret_injected_solutions_using_labels=True,
        return_shape="map_ids_object",
        route_end_strategy="round_trip",
        ctx=None,
        vehicle=None,
    )


def test_build_request_groups_same_address_orders_and_dedupes_injected_routes():
    context = _make_context(with_existing_stops=True)

    request = build_request(context)

    assert len(request.shipments) == 2
    grouped_shipment = request.shipments[0]
    singleton_shipment = request.shipments[1]

    assert [member.order_id for member in grouped_shipment.members] == [101, 102]
    assert grouped_shipment.service_duration_seconds == 10
    assert grouped_shipment.time_windows == []

    assert [member.order_id for member in singleton_shipment.members] == [103]
    assert singleton_shipment.service_duration_seconds == 5
    assert len(singleton_shipment.time_windows) == 1

    assert request.injected_routes == [
        {
            "vehicle_label": "vehicle-20",
            "visits": [
                {"shipment_label": grouped_shipment.label},
                {"shipment_label": singleton_shipment.label},
            ],
        }
    ]


def test_build_request_derives_global_bounds_from_team_local_route_times():
    context = _make_context(with_existing_stops=True)
    context.route_solution.set_start_time = "17:00"
    context.route_solution.set_end_time = "21:00"
    context.identity = {"time_zone": "Europe/Stockholm"}

    request = build_request(context)

    assert request.global_start_time == datetime(2026, 3, 8, 16, 0, tzinfo=timezone.utc)
    assert request.global_end_time == datetime(2026, 3, 8, 20, 0, tzinfo=timezone.utc)


def test_build_request_clamps_singleton_windows_and_pre_skips_no_overlap():
    context = _make_context(with_existing_stops=True)
    context.incoming_data["global_start_time"] = "2026-03-08T09:00:00Z"
    context.incoming_data["global_end_time"] = "2026-03-08T09:15:00Z"

    request = build_request(context)

    assert len(request.shipments) == 2
    singleton = request.shipments[1]
    assert len(singleton.time_windows) == 1
    assert singleton.time_windows[0].start_time.isoformat() == "2026-03-08T09:00:00+00:00"
    assert singleton.time_windows[0].end_time.isoformat() == "2026-03-08T09:15:00+00:00"

    context.incoming_data["global_start_time"] = "2026-03-08T10:30:00Z"
    context.incoming_data["global_end_time"] = "2026-03-08T11:00:00Z"
    request = build_request(context)

    assert len(request.shipments) == 1
    assert [member.order_id for member in request.shipments[0].members] == [101, 102]
    assert request.pre_skipped_shipments
    assert request.pre_skipped_shipments[0].shipment_label.startswith("group:30:57.710000,11.980000")


def test_google_mapper_preserves_grouped_shipment_labels():
    context = _make_context(with_existing_stops=False)
    request = build_request(context)

    payload = GoogleRequestMapper.build_request("projects/test", request)

    assert payload["model"]["shipments"][0]["label"] == request.shipments[0].label
    assert payload["model"]["shipments"][1]["label"] == request.shipments[1].label

    parsed = GoogleResponseMapper.parse_response(
        {
            "routes": [
                {
                    "visits": [
                        {"shipment_label": request.shipments[0].label, "arrival_time": "2026-03-08T08:00:00Z"},
                        {"shipment_label": request.shipments[1].label, "arrival_time": "2026-03-08T08:30:00Z"},
                    ],
                    "transitions": [{}, {}, {}],
                }
            ]
        },
        request,
    )

    assert parsed.stops[0].shipment_label == request.shipments[0].label
    assert parsed.stops[1].shipment_label == request.shipments[1].label


def test_persist_solution_expands_grouped_shipments_and_applies_time_warnings(monkeypatch):
    context = _make_context(with_existing_stops=False)
    request = build_request(context)

    monkeypatch.setattr(persister_module.db.session, "add", lambda *args, **kwargs: None)
    monkeypatch.setattr(persister_module.db.session, "flush", lambda *args, **kwargs: None)
    monkeypatch.setattr(persister_module.db.session, "commit", lambda *args, **kwargs: None)

    persister_module.persist_solution(
        context=context,
        request=request,
        result=OptimizationResult(
            total_distance_meters=1500,
            total_duration_seconds=2400,
            expected_start_time="2026-03-08T08:00:00Z",
            expected_end_time="2026-03-08T08:45:00Z",
            stops=[
                StopResult(
                    shipment_label=request.shipments[0].label,
                    stop_order=1,
                    expected_arrival_time=datetime(2026, 3, 8, 8, 0, tzinfo=timezone.utc),
                    in_range=True,
                ),
                StopResult(
                    shipment_label=request.shipments[1].label,
                    stop_order=2,
                    expected_arrival_time=datetime(2026, 3, 8, 8, 30, tzinfo=timezone.utc),
                    in_range=True,
                ),
            ],
            skipped=[],
            transition_polylines=["start-poly", "between-poly", "end-poly"],
        ),
        provider_name="google",
    )

    stops = sorted(context.route_solution.stops, key=lambda stop: stop.stop_order)
    assert [stop.order_id for stop in stops] == [101, 102, 103]
    assert [stop.stop_order for stop in stops] == [1, 2, 3]
    assert stops[0].expected_arrival_time.isoformat() == "2026-03-08T08:00:00+00:00"
    assert stops[1].expected_arrival_time.isoformat() == "2026-03-08T08:00:05+00:00"
    assert stops[2].expected_arrival_time.isoformat() == "2026-03-08T08:30:00+00:00"
    assert stops[0].to_next_polyline is None
    assert stops[1].to_next_polyline == "between-poly"
    assert stops[2].to_next_polyline is None
    assert context.route_solution.start_leg_polyline == "start-poly"
    assert context.route_solution.end_leg_polyline == "end-poly"
    assert stops[1].has_constraint_violation is True
    assert stops[1].constraint_warnings


def test_persist_solution_expands_skipped_grouped_shipment(monkeypatch):
    context = _make_context(with_existing_stops=False)
    request = build_request(context)

    monkeypatch.setattr(persister_module.db.session, "add", lambda *args, **kwargs: None)
    monkeypatch.setattr(persister_module.db.session, "flush", lambda *args, **kwargs: None)
    monkeypatch.setattr(persister_module.db.session, "commit", lambda *args, **kwargs: None)

    persister_module.persist_solution(
        context=context,
        request=request,
        result=OptimizationResult(
            total_distance_meters=0,
            total_duration_seconds=0,
            expected_start_time="2026-03-08T08:00:00Z",
            expected_end_time="2026-03-08T08:00:00Z",
            stops=[],
            skipped=[SkippedShipment(shipment_label=request.shipments[0].label, reason=["NO_CAPACITY"])],
            transition_polylines=[],
        ),
        provider_name="google",
    )

    stops = sorted(context.route_solution.stops, key=lambda stop: stop.stop_order)
    assert [stop.order_id for stop in stops] == [101, 102]
    assert all(stop.eta_status == "stale" for stop in stops)
    assert all(stop.in_range is False for stop in stops)


def test_persist_solution_applies_pre_skipped_optimization_window_warning(monkeypatch):
    context = _make_context(with_existing_stops=False)
    context.incoming_data["global_start_time"] = "2026-03-08T10:30:00Z"
    context.incoming_data["global_end_time"] = "2026-03-08T11:00:00Z"
    request = build_request(context)

    monkeypatch.setattr(persister_module.db.session, "add", lambda *args, **kwargs: None)
    monkeypatch.setattr(persister_module.db.session, "flush", lambda *args, **kwargs: None)
    monkeypatch.setattr(persister_module.db.session, "commit", lambda *args, **kwargs: None)

    persister_module.persist_solution(
        context=context,
        request=request,
        result=OptimizationResult(
            total_distance_meters=0,
            total_duration_seconds=0,
            expected_start_time="2026-03-08T10:30:00Z",
            expected_end_time="2026-03-08T11:00:00Z",
            stops=[],
            skipped=[],
            transition_polylines=[],
        ),
        provider_name="google",
    )

    skipped_stop = max(context.route_solution.stops, key=lambda stop: stop.stop_order)
    assert skipped_stop.order_id == 103
    assert skipped_stop.reason_was_skipped == "This order falls outside the selected optimization time range."
    assert skipped_stop.has_constraint_violation is True
    assert skipped_stop.constraint_warnings
    assert skipped_stop.constraint_warnings[0]["type"] == "optimization_window_excluded"
    assert skipped_stop.constraint_warnings[0]["allowed_start"] == "2026-03-08T08:30:00+00:00"
    assert skipped_stop.constraint_warnings[0]["allowed_end"] == "2026-03-08T09:30:00+00:00"


def test_persist_solution_temporarily_displaces_existing_stop_orders_before_swap(monkeypatch):
    order_1 = _make_order(order_id=101, lat=57.7, lng=11.97)
    order_2 = _make_order(order_id=102, lat=57.71, lng=11.98)
    route_plan = SimpleNamespace(
        id=10,
        start_date=datetime(2026, 3, 8, 8, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 3, 8, 18, 0, tzinfo=timezone.utc),
    )
    route_group = SimpleNamespace(id=20, team_id=3, route_plan=route_plan)
    route_solution = SimpleNamespace(
        id=30,
        client_id="route_solution_30",
        label="Route 30",
        is_selected=False,
        stops=[_make_route_stop(201, 101, 1), _make_route_stop(202, 102, 2)],
        start_location={
            "street_address": "Depot Street 1",
            "country": "Sweden",
            "coordinates": {"lat": 57.69, "lng": 11.96},
        },
        end_location=None,
        stops_service_time={"time": 5, "per_item": 0},
        set_start_time=None,
        set_end_time=None,
        start_leg_polyline=None,
        end_leg_polyline=None,
        total_distance_meters=None,
        total_travel_time_seconds=None,
        expected_start_time=None,
        expected_end_time=None,
        score=None,
        algorithm=None,
        is_optimized=None,
        has_route_warnings=False,
        route_warnings=None,
        stop_count=0,
        driver_id=None,
        route_group_id=20,
        route_group=route_group,
        start_location_id=None,
        vehicle_id=None,
    )
    context = SimpleNamespace(
        route_plan=route_plan,
        route_group=route_group,
        route_solution=route_solution,
        orders=[order_1, order_2],
        identity={},
        incoming_data={},
        interpret_injected_solutions_using_labels=True,
        return_shape="map_ids_object",
        route_end_strategy="round_trip",
        ctx=None,
    )
    request = OptimizationRequest(
        route_plan_id=10,
        route_group_id=20,
        route_solution_id=30,
        shipments=[
            Shipment(
                label="group:30:first",
                location={"latitude": 57.70, "longitude": 11.97},
                members=[ShipmentMember(order_id=101, service_duration_seconds=0)],
                service_duration_seconds=0,
            ),
            Shipment(
                label="group:30:second",
                location={"latitude": 57.71, "longitude": 11.98},
                members=[ShipmentMember(order_id=102, service_duration_seconds=0)],
                service_duration_seconds=0,
            ),
        ],
        start_location=route_solution.start_location,
        end_location=route_solution.end_location,
        start_coordinates={"latitude": 57.69, "longitude": 11.96},
        end_coordinates={"latitude": 57.69, "longitude": 11.96},
        global_start_time=None,
        global_end_time=None,
        consider_traffic=False,
        route_modifiers={},
        objectives=[],
        travel_mode="DRIVE",
        cost_per_kilometer=1.0,
        populate_transition_polylines=False,
    )

    flush_snapshots = []

    monkeypatch.setattr(persister_module.db.session, "add", lambda *args, **kwargs: None)

    def _flush(*args, **kwargs):
        flush_snapshots.append(
            [(stop.id, stop.order_id, stop.stop_order) for stop in route_solution.stops]
        )

    monkeypatch.setattr(persister_module.db.session, "flush", _flush)
    monkeypatch.setattr(persister_module.db.session, "commit", lambda *args, **kwargs: None)

    persister_module.persist_solution(
        context=context,
        request=request,
        result=OptimizationResult(
            total_distance_meters=100,
            total_duration_seconds=200,
            expected_start_time=datetime(2026, 3, 8, 8, 0, tzinfo=timezone.utc),
            expected_end_time=datetime(2026, 3, 8, 8, 10, tzinfo=timezone.utc),
            stops=[
                StopResult(
                    shipment_label="group:30:second",
                    stop_order=1,
                    expected_arrival_time=datetime(2026, 3, 8, 8, 0, tzinfo=timezone.utc),
                    in_range=True,
                ),
                StopResult(
                    shipment_label="group:30:first",
                    stop_order=2,
                    expected_arrival_time=datetime(2026, 3, 8, 8, 5, tzinfo=timezone.utc),
                    in_range=True,
                ),
            ],
            skipped=[],
            transition_polylines=[],
        ),
        provider_name="google",
    )

    assert len(flush_snapshots) >= 2
    first_flush_orders = [stop_order for _, _, stop_order in flush_snapshots[0]]
    assert all(stop_order >= 1000 for stop_order in first_flush_orders)

    final_stops = sorted(route_solution.stops, key=lambda stop: stop.stop_order or 0)
    assert [(stop.order_id, stop.stop_order) for stop in final_stops] == [
        (102, 1),
        (101, 2),
    ]
