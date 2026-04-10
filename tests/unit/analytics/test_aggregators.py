from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from Delivery_app_BK.analytics.aggregators.daily_aggregator import aggregate_daily_metrics
from Delivery_app_BK.analytics.aggregators.route_aggregator import compute_route_metrics
from Delivery_app_BK.services.domain.order.order_states import OrderStateId


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *_args, **_kwargs):
        return self

    def distinct(self):
        return self

    def all(self):
        return list(self._rows)


class _FakeSession:
    def __init__(self, mapping):
        self._mapping = mapping

    def query(self, model):
        return _FakeQuery(self._mapping.get(getattr(model, "__name__", ""), []))


def test_compute_route_metrics_calculates_delay_and_rate_metrics(monkeypatch):
    expected_start = datetime(2026, 3, 25, 8, 0, tzinfo=timezone.utc)

    stop_early = SimpleNamespace(
        actual_arrival_time=expected_start,
        expected_arrival_time=expected_start + timedelta(minutes=10),
        expected_service_duration_seconds=120,
    )
    stop_on_time = SimpleNamespace(
        actual_arrival_time=expected_start + timedelta(minutes=30),
        expected_arrival_time=expected_start + timedelta(minutes=28),
        expected_service_duration_seconds=300,
    )
    stop_late = SimpleNamespace(
        actual_arrival_time=expected_start + timedelta(minutes=60),
        expected_arrival_time=expected_start + timedelta(minutes=45),
        expected_service_duration_seconds=180,
    )
    stop_unmeasured = SimpleNamespace(
        actual_arrival_time=None,
        expected_arrival_time=expected_start + timedelta(minutes=70),
        expected_service_duration_seconds=90,
    )

    fake_route = SimpleNamespace(
        id=99,
        team_id=3,
        expected_start_time=expected_start,
        total_distance_meters=15000,
        total_travel_time_seconds=3600,
        stops=[stop_early, stop_on_time, stop_late, stop_unmeasured],
    )

    fake_db = SimpleNamespace(session=SimpleNamespace(get=lambda *_args, **_kwargs: fake_route))
    monkeypatch.setattr(
        "Delivery_app_BK.analytics.aggregators.route_aggregator.db",
        fake_db,
    )
    monkeypatch.setattr(
        "Delivery_app_BK.analytics.aggregators.route_aggregator.derive_route_zone",
        lambda _route: (None, None),
    )

    snapshot = compute_route_metrics(route_solution_id=99)

    assert snapshot is not None
    assert snapshot.total_stops == 4
    assert snapshot.on_time_stops == 1
    assert snapshot.early_stops == 1
    assert snapshot.late_stops == 1
    assert snapshot.avg_delay_seconds == 140.0
    assert snapshot.max_delay_seconds == 900.0
    assert snapshot.on_time_rate == 0.25
    assert snapshot.delay_rate == 0.25
    assert snapshot.total_service_time_seconds == 690.0
    assert snapshot.total_orders == 4


def test_compute_route_metrics_returns_none_when_route_missing(monkeypatch):
    fake_db = SimpleNamespace(session=SimpleNamespace(get=lambda *_args, **_kwargs: None))
    monkeypatch.setattr(
        "Delivery_app_BK.analytics.aggregators.route_aggregator.db",
        fake_db,
    )

    assert compute_route_metrics(route_solution_id=404) is None


def test_aggregate_daily_metrics_combines_order_and_route_snapshots(monkeypatch):
    orders = [
        SimpleNamespace(order_state_id=OrderStateId.COMPLETED, route_plan_id=10),
        SimpleNamespace(order_state_id=OrderStateId.FAIL, route_plan_id=11),
        SimpleNamespace(order_state_id=OrderStateId.DRAFT, route_plan_id=None),
        SimpleNamespace(order_state_id=OrderStateId.DRAFT, route_plan_id=12),
    ]
    routes = [
        SimpleNamespace(id=1, actual_end_time=datetime(2026, 3, 25, 12, 0, tzinfo=timezone.utc)),
        SimpleNamespace(id=2, actual_end_time=None),
    ]
    snapshots = [
        SimpleNamespace(
            avg_delay_seconds=100.0,
            delay_rate=0.1,
            total_distance_meters=1000.0,
            total_travel_time_seconds=600.0,
        ),
        SimpleNamespace(
            avg_delay_seconds=50.0,
            delay_rate=0.0,
            total_distance_meters=3000.0,
            total_travel_time_seconds=1200.0,
        ),
    ]

    fake_session = _FakeSession(
        {
            "Order": orders,
            "RouteSolution": routes,
            "RouteMetricsSnapshot": snapshots,
        }
    )
    monkeypatch.setattr(
        "Delivery_app_BK.analytics.aggregators.daily_aggregator.db",
        SimpleNamespace(session=fake_session),
    )

    metrics = aggregate_daily_metrics(
        team_id=3,
        target_date=date(2026, 3, 25),
        team_timezone="UTC",
        zone_id=None,
    )

    assert metrics.total_orders_created == 4
    assert metrics.total_orders_completed == 1
    assert metrics.total_orders_failed == 1
    assert metrics.scheduled_orders == 3
    assert metrics.unscheduled_orders == 1
    assert metrics.completion_rate == 0.25

    assert metrics.total_routes == 2
    assert metrics.routes_completed == 1
    assert metrics.routes_active == 1
    assert metrics.avg_delay_seconds == 75.0
    assert metrics.late_routes_count == 1
    assert metrics.on_time_routes_count == 1
    assert metrics.total_distance_meters == 4000.0
    assert metrics.total_travel_time_seconds == 1800.0
