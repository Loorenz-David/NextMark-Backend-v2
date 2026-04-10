from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.route_optimization.services import request_builder as module


def _build_context():
    return SimpleNamespace(
        incoming_data={
            "global_start_time": "2026-03-05T00:00:00+00:00",
            "global_end_time": "2026-03-06T23:59:59+00:00",
        },
        route_plan=SimpleNamespace(
            start_date=datetime(2026, 3, 5, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2026, 3, 6, 23, 59, tzinfo=timezone.utc),
        ),
        route_solution=SimpleNamespace(set_start_time=None, set_end_time=None),
    )


def test_build_time_windows_uses_delivery_windows_authoritatively():
    context = _build_context()
    order = SimpleNamespace(
        id=10,
        delivery_windows=[
            SimpleNamespace(
                start_at=datetime(2026, 3, 5, 12, 0, tzinfo=timezone.utc),
                end_at=datetime(2026, 3, 5, 13, 0, tzinfo=timezone.utc),
            ),
            SimpleNamespace(
                start_at=datetime(2026, 3, 5, 9, 0, tzinfo=timezone.utc),
                end_at=datetime(2026, 3, 5, 11, 0, tzinfo=timezone.utc),
            ),
        ],
    )

    windows = module._build_time_windows(order, context)

    assert len(windows) == 2
    assert windows[0].start_time.isoformat() == "2026-03-05T09:00:00+00:00"
    assert windows[1].start_time.isoformat() == "2026-03-05T12:00:00+00:00"


def test_build_time_windows_rejects_overlapping_delivery_windows():
    context = _build_context()
    order = SimpleNamespace(
        id=10,
        delivery_windows=[
            SimpleNamespace(
                start_at=datetime(2026, 3, 5, 9, 0, tzinfo=timezone.utc),
                end_at=datetime(2026, 3, 5, 12, 0, tzinfo=timezone.utc),
            ),
            SimpleNamespace(
                start_at=datetime(2026, 3, 5, 11, 59, tzinfo=timezone.utc),
                end_at=datetime(2026, 3, 5, 13, 0, tzinfo=timezone.utc),
            ),
        ],
    )

    with pytest.raises(ValidationFailed):
        module._build_time_windows(order, context)


def test_build_time_windows_rejects_above_max_delivery_windows():
    context = _build_context()
    windows = []
    for idx in range(15):
        windows.append(
            SimpleNamespace(
                start_at=datetime(2026, 3, 5, idx, 0, tzinfo=timezone.utc),
                end_at=datetime(2026, 3, 5, idx, 30, tzinfo=timezone.utc),
            ),
        )
    order = SimpleNamespace(
        id=10,
        delivery_windows=windows,
    )

    with pytest.raises(ValidationFailed):
        module._build_time_windows(order, context)


def test_build_time_windows_returns_empty_when_no_delivery_windows():
    context = _build_context()
    order = SimpleNamespace(
        id=10,
        delivery_windows=[],
    )

    windows = module._build_time_windows(order, context)

    assert windows == []
