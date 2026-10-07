from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from Delivery_app_BK.services.commands.route_plan.local_delivery import arrival_tracking as module
from Delivery_app_BK.services.domain.order.order_states import OrderStateId

T0 = datetime(2026, 10, 19, 8, 30, tzinfo=timezone.utc)
READY = OrderStateId.READY
CONFIRMED = OrderStateId.CONFIRMED


def _install(monkeypatch, *, after, orders):
    monkeypatch.setattr(module, "load_selected_order_arrivals", lambda **_kwargs: after)

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self

        def all(self):
            return orders

    monkeypatch.setattr(module, "db", SimpleNamespace(session=SimpleNamespace(query=lambda *_a: _Query())))


def _snapshot(before):
    return module.ArrivalSnapshot(team_id=7, route_group_ids=frozenset({3}), arrivals=before)


def _order(order_id, state_id):
    return SimpleNamespace(id=order_id, team_id=7, order_state_id=state_id)


def test_moved_arrivals_become_history_and_ready_customers_are_rescheduled(monkeypatch):
    _install(
        monkeypatch,
        after={1: T0 + timedelta(minutes=40), 2: T0 + timedelta(minutes=50), 3: T0 + timedelta(hours=2)},
        orders=[_order(1, CONFIRMED), _order(2, READY), _order(3, CONFIRMED)],
    )

    outcome = module.collect_arrival_changes(
        _snapshot({1: T0, 2: T0, 3: T0}), cause="stops_reordered"
    )

    by_order = {event["order_id"]: event for event in outcome.events}
    assert by_order[1]["event_name"] == "order_arrival_changed"
    assert by_order[1]["payload"]["cause"] == "stops_reordered"
    assert by_order[1]["payload"]["old_expected_arrival"] == T0.isoformat()
    # Ready: the customer-facing reschedule, quiet because the route notifies.
    assert by_order[2]["event_name"] == "order_rescheduled"
    assert by_order[2]["payload"]["reason"] == "eta_changed"
    assert by_order[2]["payload"]["notification_suppressed"] is True
    assert outcome.notification_payload["notification_arrival_change_count"] == 3
    assert [entry["order_id"] for entry in outcome.notification_payload["notification_arrival_changes"]] == [1, 2]


def test_a_first_arrival_only_reaches_ready_customers(monkeypatch):
    _install(
        monkeypatch,
        after={1: T0, 2: T0},
        orders=[_order(1, CONFIRMED), _order(2, READY)],
    )

    outcome = module.collect_arrival_changes(_snapshot({}), cause="settings_updated")

    assert [(e["order_id"], e["event_name"]) for e in outcome.events] == [(2, "order_rescheduled")]
    # Nothing moved, so the route notification has no arrival line.
    assert outcome.notification_payload == {}


def test_no_snapshot_means_nothing_to_report():
    assert module.collect_arrival_changes(None, cause="stops_reordered") == module.ArrivalChangeOutcome()
