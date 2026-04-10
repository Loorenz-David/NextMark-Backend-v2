"""Local Delivery App Service Layer.

Handles all local delivery plan-specific logic for order objectives, plan changes,
and order update/delete extensions. Provides explicit app-scoped service implementations
instead of relying on string-based dispatcher patterns.
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
