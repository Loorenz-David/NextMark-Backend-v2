from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Callable

from Delivery_app_BK.models import (
    InternationalShippingPlan,
    RouteGroup,
    RouteSolution,
    StorePickupPlan,
)


@dataclass
class PlanChangeApplyContext:
    route_groups_by_route_plan_id: dict[int, list[RouteGroup]] = field(default_factory=dict)
    route_solutions_by_route_group_id: dict[int, list[RouteSolution]] = field(
        default_factory=dict
    )
    source_route_group_id_by_order_id: dict[int, int] = field(default_factory=dict)
    destination_route_group_id_by_order_id: dict[int, int] = field(default_factory=dict)
    international_shipping_by_plan_id: dict[int, InternationalShippingPlan] = field(
        default_factory=dict
    )
    store_pickup_by_plan_id: dict[int, StorePickupPlan] = field(default_factory=dict)


@dataclass
class PlanChangeResult:
    instances: list[object] = field(default_factory=list)
    post_flush_actions: list[Callable[[], None]] = field(default_factory=list)
    bundle_serializer: Callable[[], dict] | None = None

    def serialize_bundle(self) -> dict:
        if not self.bundle_serializer:
            return {}
        return self.bundle_serializer()
