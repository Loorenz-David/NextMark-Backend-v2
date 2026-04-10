"""International Shipping App - Order Delete Extension Handler (no-op).

International shipping plans do not require custom order delete processing.
"""

from ...context import ServiceContext
from ..order.delete_extensions.types import OrderDeleteDelta, OrderDeleteExtensionContext, OrderDeleteExtensionResult


def apply_order_delete_extension(
    ctx: ServiceContext,
    delete_deltas: list[OrderDeleteDelta],
    extension_context: OrderDeleteExtensionContext,
) -> OrderDeleteExtensionResult:
    """International shipping plans don't require order delete processing.
    
    Returns an empty result.
    """
    return OrderDeleteExtensionResult()
