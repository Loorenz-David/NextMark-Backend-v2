from __future__ import annotations

from typing import Any

from .changes import OrderFieldChange, audit_values_differ

ROUTE_PLAN_FIELD = "route_plan_id"
DELIVERY_DATES_FIELD = "delivery_dates"


def plan_move_changes(
    *,
    old_plan_id: int | None,
    new_plan_id: int | None,
    old_plan_start: str | None,
    old_plan_end: str | None,
    new_plan_start: str | None,
    new_plan_end: str | None,
) -> list[OrderFieldChange]:
    """What moving an order between plans changed: the plan and, when the
    plans fall on different days, its delivery dates (ISO strings)."""
    changes: list[OrderFieldChange] = []
    if audit_values_differ(old_plan_id, new_plan_id):
        changes.append(OrderFieldChange(ROUTE_PLAN_FIELD, old_plan_id, new_plan_id))

    old_dates = _dates(old_plan_start, old_plan_end)
    new_dates = _dates(new_plan_start, new_plan_end)
    if audit_values_differ(old_dates, new_dates):
        changes.append(OrderFieldChange(DELIVERY_DATES_FIELD, old_dates, new_dates))
    return changes


def _dates(start: str | None, end: str | None) -> dict[str, Any] | None:
    if not start:
        return None
    return {"start": start, "end": end}
