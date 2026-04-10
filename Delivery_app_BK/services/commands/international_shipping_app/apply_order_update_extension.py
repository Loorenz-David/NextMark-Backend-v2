"""International Shipping App - Order Update Extension Handler (no-op).

International shipping plans do not require custom order update processing.
"""

from ...context import ServiceContext
from ..order.update_extensions.types import OrderUpdateDelta, OrderUpdateExtensionContext, OrderUpdateExtensionResult


def apply_order_update_extension(
    ctx: ServiceContext,
    order_deltas: list[OrderUpdateDelta],
    extension_context: OrderUpdateExtensionContext,
) -> OrderUpdateExtensionResult:
    """International shipping plans don't require order update processing.
    
    Returns an empty result.
    """
    return OrderUpdateExtensionResult()
