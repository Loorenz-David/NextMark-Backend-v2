"""Record arrival-time changes caused by a route action.

Usage: take `snapshot_route_arrivals` before the action touches the route,
then `collect_arrival_changes` after it (post-flush or post-commit) and emit
`outcome.events` once committed. Pass `outcome.notification_payload` into the
action's one route/plan notification so it can say what moved.

Every order whose arrival moved gets a history entry. Ready orders get the
customer-facing DELIVERY_RESCHEDULED (reason "eta_changed") instead — also
when they get their first arrival — which may message the customer; it is
marked so it does not notify on its own.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

from Delivery_app_BK.models import Order, db
from Delivery_app_BK.services.domain.order.order_states import OrderStateId
from Delivery_app_BK.services.domain.route_operations.local_delivery.arrival_changes import (
    diff_order_arrivals,
)
from Delivery_app_BK.services.infra.events.builders.order import (
    build_delivery_rescheduled_event,
    build_order_arrival_changed_event,
)
from Delivery_app_BK.services.queries.route_solutions.selected_order_arrivals import (
    load_selected_order_arrivals,
)

ARRIVAL_PREVIEW_LIMIT = 2


@dataclass(frozen=True)
class ArrivalSnapshot:
    team_id: int
    route_group_ids: frozenset[int]
    arrivals: dict[int, datetime | None]


@dataclass(frozen=True)
class ArrivalChangeOutcome:
    events: list[dict] = field(default_factory=list)
    notification_payload: dict = field(default_factory=dict)


def snapshot_route_arrivals(
    team_id: int | None,
    route_group_ids: Iterable[int | None],
) -> ArrivalSnapshot | None:
    group_ids = frozenset(group_id for group_id in route_group_ids if group_id is not None)
    if team_id is None or not group_ids:
        return None
    return ArrivalSnapshot(
        team_id=team_id,
        route_group_ids=group_ids,
        arrivals=load_selected_order_arrivals(team_id=team_id, route_group_ids=group_ids),
    )


def collect_arrival_changes(
    snapshot: ArrivalSnapshot | None,
    *,
    cause: str,
    exclude_order_ids: Iterable[int] = (),
) -> ArrivalChangeOutcome:
    """`exclude_order_ids`: orders whose own event already reports the move
    (e.g. the order that was moved to another plan)."""
    if snapshot is None:
        return ArrivalChangeOutcome()

    after = load_selected_order_arrivals(
        team_id=snapshot.team_id,
        route_group_ids=snapshot.route_group_ids,
    )
    changes = diff_order_arrivals(
        snapshot.arrivals,
        after,
        exclude_order_ids=frozenset(exclude_order_ids),
    )
    if not changes:
        return ArrivalChangeOutcome()

    orders_by_id = {
        order.id: order
        for order in db.session.query(Order)
        .filter(
            Order.team_id == snapshot.team_id,
            Order.id.in_([change.order_id for change in changes]),
        )
        .all()
    }

    events: list[dict] = []
    reported: list = []
    for change in changes:
        order = orders_by_id.get(change.order_id)
        if order is None:
            continue
        is_ready = order.order_state_id == OrderStateId.READY
        if change.is_first_arrival and not is_ready:
            continue
        reported.append(change)
        if is_ready:
            event = build_delivery_rescheduled_event(
                order,
                old_expected_arrival=change.old_arrival,
                new_expected_arrival=change.new_arrival,
                reason="eta_changed",
            )
            # The route action's own notification reports it.
            event["payload"]["notification_suppressed"] = True
        else:
            event = build_order_arrival_changed_event(
                order,
                old_expected_arrival=change.old_arrival,
                new_expected_arrival=change.new_arrival,
                cause=cause,
            )
        events.append(event)

    moved = [change for change in reported if not change.is_first_arrival]
    if not moved:
        return ArrivalChangeOutcome(events=events)
    return ArrivalChangeOutcome(
        events=events,
        notification_payload={
            "notification_arrival_change_count": len(moved),
            "notification_arrival_changes": [
                {
                    "order_id": change.order_id,
                    "old_arrival": change.old_arrival.isoformat(),
                    "new_arrival": change.new_arrival.isoformat(),
                }
                for change in moved[:ARRIVAL_PREVIEW_LIMIT]
            ],
        },
    )
