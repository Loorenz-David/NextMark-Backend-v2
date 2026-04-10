"""International Shipping App Service Layer.

Handles international shipping plan-specific logic. Currently no custom orchestration
for order objectives, plan changes, or extensions (all no-op).
"""

from .apply_order_objective import apply_order_objective
from .apply_order_plan_change import apply_order_plan_change
from .apply_order_update_extension import apply_order_update_extension
from .apply_order_delete_extension import apply_order_delete_extension

__all__ = [
    "apply_order_objective",
    "apply_order_plan_change",
    "apply_order_update_extension",
    "apply_order_delete_extension",
]
