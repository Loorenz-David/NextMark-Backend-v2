from types import SimpleNamespace

from Delivery_app_BK.services.infra.jobs.tasks.analytics import compute_route_metrics_job


def test_compute_route_metrics_job_persists_when_snapshot_exists(monkeypatch):
    captured = {"persisted": None}
    snapshot = SimpleNamespace(route_solution_id=123)

    monkeypatch.setattr(
        "Delivery_app_BK.analytics.aggregators.route_aggregator.compute_route_metrics",
        lambda route_solution_id: snapshot if route_solution_id == 123 else None,
    )
    monkeypatch.setattr(
        "Delivery_app_BK.analytics.aggregators.route_aggregator.persist_route_metrics",
        lambda s: captured.__setitem__("persisted", s),
    )

    compute_route_metrics_job(123)

    assert captured["persisted"] is snapshot


def test_compute_route_metrics_job_skips_persist_when_snapshot_missing(monkeypatch):
    called = {"persist": 0}

    monkeypatch.setattr(
        "Delivery_app_BK.analytics.aggregators.route_aggregator.compute_route_metrics",
        lambda _route_solution_id: None,
    )
    monkeypatch.setattr(
        "Delivery_app_BK.analytics.aggregators.route_aggregator.persist_route_metrics",
        lambda _snapshot: called.__setitem__("persist", called["persist"] + 1),
    )

    compute_route_metrics_job(999)

    assert called["persist"] == 0
