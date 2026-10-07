from datetime import datetime, timedelta, timezone

from Delivery_app_BK.services.domain.route_operations.local_delivery.arrival_changes import (
    diff_order_arrivals,
)

T0 = datetime(2026, 10, 19, 8, 30, tzinfo=timezone.utc)


def test_moved_arrivals_are_reported_earliest_first():
    changes = diff_order_arrivals(
        {1: T0, 2: T0 + timedelta(hours=1)},
        {1: T0 + timedelta(minutes=40), 2: T0 + timedelta(minutes=10)},
    )

    assert [(c.order_id, c.old_arrival, c.new_arrival) for c in changes] == [
        (2, T0 + timedelta(hours=1), T0 + timedelta(minutes=10)),
        (1, T0, T0 + timedelta(minutes=40)),
    ]


def test_seconds_of_recompute_noise_are_not_a_change():
    assert diff_order_arrivals({1: T0}, {1: T0 + timedelta(seconds=40)}) == []


def test_first_arrivals_are_reported_and_lost_ones_are_not():
    changes = diff_order_arrivals({2: T0}, {1: T0, 2: None})

    assert [(c.order_id, c.is_first_arrival) for c in changes] == [(1, True)]


def test_excluded_orders_are_left_to_their_own_event():
    assert diff_order_arrivals(
        {1: T0}, {1: T0 + timedelta(hours=1)}, exclude_order_ids=frozenset({1})
    ) == []
