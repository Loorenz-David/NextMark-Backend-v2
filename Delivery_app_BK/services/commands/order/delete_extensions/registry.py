from __future__ import annotations

from collections.abc import Callable

from ....context import ServiceContext
from .types import OrderDeleteDelta, OrderDeleteExtensionContext, OrderDeleteExtensionResult


OrderDeleteExtensionHandler = Callable[
    [ServiceContext, list[OrderDeleteDelta], OrderDeleteExtensionContext],
    OrderDeleteExtensionResult,
]


def resolve_delete_extension_handler(
    plan_type: str,
) -> OrderDeleteExtensionHandler | None:
    if plan_type == "local_delivery":
        from ...local_delivery_app.apply_order_delete_extension import (
            apply_order_delete_extension,
        )

        return apply_order_delete_extension

    if plan_type == "store_pickup":
        from ...store_pickup_app.apply_order_delete_extension import (
            apply_order_delete_extension,
        )

        return apply_order_delete_extension

    if plan_type == "international_shipping":
        from ...international_shipping_app.apply_order_delete_extension import (
            apply_order_delete_extension,
        )

        return apply_order_delete_extension

    return None
