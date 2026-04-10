"""Compatibility shim for legacy app-scoped imports.

Use `services.commands.order.plan_changes.route_plan_change.apply_route_plan_change`
for new code.
"""

from ..order.plan_changes.route_plan_change import apply_route_plan_change


def apply_order_plan_change(*args, **kwargs):
    return apply_route_plan_change(*args, **kwargs)


__all__ = ["apply_order_plan_change"]
