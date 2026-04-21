from types import SimpleNamespace

import Delivery_app_BK.services.domain.route_operations.local_delivery.route_lifecycle as module


def test_stage_route_solution_stop_order_updates_uses_two_phase_flush(monkeypatch):
    stop_a = SimpleNamespace(id=1, stop_order=2)
    stop_b = SimpleNamespace(id=2, stop_order=1)

    added_batches = []
    snapshots = []

    def _add_all(stops):
        batch = list(stops)
        added_batches.append([stop.id for stop in batch])
        snapshots.append([(stop.id, stop.stop_order) for stop in batch])

    monkeypatch.setattr(
        module,
        "db",
        SimpleNamespace(
            session=SimpleNamespace(
                add_all=_add_all,
                flush=lambda: None,
            )
        ),
    )

    module.stage_route_solution_stop_order_updates([stop_a, stop_b])

    assert snapshots[0] == [(1, -1), (2, -2)]
    assert snapshots[1] == [(1, 2), (2, 1)]
    assert stop_a.stop_order == 2
    assert stop_b.stop_order == 1
