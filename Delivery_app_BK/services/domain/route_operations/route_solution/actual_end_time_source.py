from __future__ import annotations

from enum import Enum


class RouteActualEndTimeSource(str, Enum):
    EXPECTED = "expected"
    LAST_ORDER_PROJECTION = "last_order_projection"
    MANUAL_COMPLETION = "manual_completion"

    @classmethod
    def values(cls) -> tuple[str, ...]:
        return tuple(member.value for member in cls)
