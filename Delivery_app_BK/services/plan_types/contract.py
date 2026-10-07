from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from Delivery_app_BK.models import Order, RoutePlan

    from ..commands.order.delete_extensions.types import (
        OrderDeleteDelta,
        OrderDeleteExtensionContext,
        OrderDeleteExtensionResult,
    )
    from ..commands.order.plan_changes.types import PlanChangeApplyContext, PlanChangeResult
    from ..commands.order.plan_objectives.types import PlanObjectiveCreateResult
    from ..commands.order.update_extensions.types import (
        OrderUpdateDelta,
        OrderUpdateExtensionContext,
        OrderUpdateExtensionResult,
    )
    from ..context import ServiceContext

    PlanObjectiveHandler = Callable[
        [ServiceContext, Order, RoutePlan, str],
        PlanObjectiveCreateResult,
    ]
    PlanChangeHandler = Callable[
        [ServiceContext, Order, RoutePlan | None, RoutePlan | None, PlanChangeApplyContext],
        PlanChangeResult,
    ]
    OrderUpdateHandler = Callable[
        [ServiceContext, list[OrderUpdateDelta], OrderUpdateExtensionContext],
        OrderUpdateExtensionResult,
    ]
    OrderDeleteHandler = Callable[
        [ServiceContext, list[OrderDeleteDelta], OrderDeleteExtensionContext],
        OrderDeleteExtensionResult,
    ]
    OrderRealtimeExtrasBuilder = Callable[[RoutePlan], dict[str, Any]]


@dataclass(frozen=True)
class PlanTypeModule:
    """Everything shared order code may ask of a plan type.

    A new hook is a new required field, so every plan type has to answer it
    explicitly — a no-op is a decision, not an omission.
    """

    plan_type: str
    # An order was assigned to a plan of this type: build its per-order artifacts.
    apply_objective: PlanObjectiveHandler
    # An order moved between plans. Only the sides that belong to this type are
    # passed; the other side is None.
    apply_plan_change: PlanChangeHandler
    # Orders on plans of this type were edited.
    apply_order_update: OrderUpdateHandler
    # Orders on plans of this type are being deleted.
    apply_order_delete: OrderDeleteHandler
    # Extra keys merged into the order realtime payload for orders on this type.
    build_order_realtime_extras: OrderRealtimeExtrasBuilder


def no_order_realtime_extras(route_plan: RoutePlan) -> dict[str, Any]:
    return {}
