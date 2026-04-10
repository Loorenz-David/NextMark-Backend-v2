"""Compatibility shim for legacy imports.

Use `route_plan_change.apply_route_plan_change` for new code.
"""

from .route_plan_change import apply_route_plan_change


def apply_local_delivery_plan_change(*args, **kwargs):
    return apply_route_plan_change(*args, **kwargs)


__all__ = ["apply_route_plan_change", "apply_local_delivery_plan_change"]
