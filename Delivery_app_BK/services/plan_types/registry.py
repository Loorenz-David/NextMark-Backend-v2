from __future__ import annotations

from functools import cache

from .contract import PlanTypeModule


@cache
def _plan_type_modules() -> dict[str, PlanTypeModule]:
    # Imported on first use: each type module binds handlers from the order
    # command packages, and those packages dispatch through this registry.
    from .international_shipping import INTERNATIONAL_SHIPPING
    from .local_delivery import LOCAL_DELIVERY
    from .store_pickup import STORE_PICKUP

    return {
        module.plan_type: module
        for module in (LOCAL_DELIVERY, STORE_PICKUP, INTERNATIONAL_SHIPPING)
    }


def get_plan_type_module(plan_type: str | None) -> PlanTypeModule | None:
    if plan_type is None:
        return None
    return _plan_type_modules().get(plan_type)
