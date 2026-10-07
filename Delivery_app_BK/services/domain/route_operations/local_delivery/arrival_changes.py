from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

# Recomputing a route moves arrivals by seconds; that is noise, not a change.
ARRIVAL_CHANGE_TOLERANCE = timedelta(minutes=1)


@dataclass(frozen=True)
class ArrivalChange:
    order_id: int
    # None when the order had no arrival before — its first one.
    old_arrival: datetime | None
    new_arrival: datetime

    @property
    def is_first_arrival(self) -> bool:
        return self.old_arrival is None


def diff_order_arrivals(
    before: Mapping[int, datetime | None],
    after: Mapping[int, datetime | None],
    *,
    exclude_order_ids: frozenset[int] = frozenset(),
) -> list[ArrivalChange]:
    """Orders whose expected arrival moved or was first set, earliest new
    arrival first. An order losing its arrival (removed, unscheduled) is
    reported by that action instead.
    """
    changes: list[ArrivalChange] = []
    for order_id, new in after.items():
        if order_id in exclude_order_ids or new is None:
            continue
        old = before.get(order_id)
        if old is not None and abs(new - old) < ARRIVAL_CHANGE_TOLERANCE:
            continue
        changes.append(ArrivalChange(order_id=order_id, old_arrival=old, new_arrival=new))
    return sorted(changes, key=lambda change: (change.new_arrival, change.order_id))
