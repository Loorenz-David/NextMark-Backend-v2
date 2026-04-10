from zoneinfo import ZoneInfo

import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.domain.order.delivery_windows import (
    validate_and_normalize_delivery_windows,
    validate_same_local_day_delivery_windows,
)


def test_validate_and_normalize_delivery_windows_sorts_and_allows_adjacent():
    rows = [
        {
            "start_at": "2026-03-05T12:00:00+00:00",
            "end_at": "2026-03-05T14:00:00+00:00",
            "window_type": "FULL_RANGE",
        },
        {
            "start_at": "2026-03-05T09:00:00+00:00",
            "end_at": "2026-03-05T12:00:00+00:00",
            "window_type": "FULL_RANGE",
        },
    ]

    normalized = validate_and_normalize_delivery_windows(rows)

    assert normalized[0].start_at.isoformat() == "2026-03-05T09:00:00+00:00"
    assert normalized[1].start_at.isoformat() == "2026-03-05T12:00:00+00:00"


def test_validate_and_normalize_delivery_windows_rejects_overlap():
    rows = [
        {
            "start_at": "2026-03-05T09:00:00+00:00",
            "end_at": "2026-03-05T12:00:00+00:00",
            "window_type": "FULL_RANGE",
        },
        {
            "start_at": "2026-03-05T11:59:00+00:00",
            "end_at": "2026-03-05T14:00:00+00:00",
            "window_type": "FULL_RANGE",
        },
    ]

    with pytest.raises(ValidationFailed):
        validate_and_normalize_delivery_windows(rows)


def test_validate_and_normalize_delivery_windows_rejects_non_utc_offsets():
    rows = [
        {
            "start_at": "2026-03-05T09:00:00+01:00",
            "end_at": "2026-03-05T10:00:00+01:00",
            "window_type": "FULL_RANGE",
        }
    ]

    with pytest.raises(ValidationFailed):
        validate_and_normalize_delivery_windows(rows)


def test_validate_same_local_day_rejects_cross_midnight_in_team_timezone():
    normalized = validate_and_normalize_delivery_windows(
        [
            {
                "start_at": "2026-03-05T22:30:00+00:00",
                "end_at": "2026-03-05T23:30:00+00:00",
                "window_type": "FULL_RANGE",
            }
        ],
    )

    # Europe/Stockholm: 22:30 UTC -> 23:30 local, 23:30 UTC -> 00:30 next day.
    with pytest.raises(ValidationFailed):
        validate_same_local_day_delivery_windows(
            normalized,
            team_timezone=ZoneInfo("Europe/Stockholm"),
        )
