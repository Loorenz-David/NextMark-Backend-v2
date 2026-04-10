from __future__ import annotations

from collections.abc import Callable

from ....context import ServiceContext
from .types import OrderUpdateDelta, OrderUpdateExtensionContext, OrderUpdateExtensionResult


OrderUpdateExtensionHandler = Callable[
    [ServiceContext, list[OrderUpdateDelta], OrderUpdateExtensionContext],
    OrderUpdateExtensionResult,
]


def resolve_update_extension_handler(
    plan_type: str,
) -> OrderUpdateExtensionHandler | None:
    if plan_type == "local_delivery":
        from ...local_delivery_app.apply_order_update_extension import (
            apply_order_update_extension,
        )

        return apply_order_update_extension

    if plan_type == "store_pickup":
        from ...store_pickup_app.apply_order_update_extension import (
            apply_order_update_extension,
        )

        return apply_order_update_extension

    if plan_type == "international_shipping":
        from ...international_shipping_app.apply_order_update_extension import (
            apply_order_update_extension,
        )

        return apply_order_update_extension

    return None
