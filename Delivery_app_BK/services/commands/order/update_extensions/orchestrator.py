from __future__ import annotations

from collections import defaultdict

from Delivery_app_BK.services.plan_types.registry import get_plan_type_module

from ....context import ServiceContext
from ..extensions import merge_bundle_map, wrap_post_flush_action
from .types import OrderUpdateDelta, OrderUpdateExtensionContext, OrderUpdateExtensionResult


def _resolve_plan_type(delta: OrderUpdateDelta) -> str | None:
    # The plan states its own type. Reading it off the order's objective meant a
    # drifted order could route its update through another domain's handler.
    # An unassigned order has no plan and therefore no extensions to run.
    return getattr(delta.delivery_plan, "plan_type", None)


def apply_order_update_extensions(
    ctx: ServiceContext,
    order_deltas: list[OrderUpdateDelta],
    extension_context: OrderUpdateExtensionContext,
) -> OrderUpdateExtensionResult:
    result = OrderUpdateExtensionResult()
    if not order_deltas:
        return result

    grouped_deltas: defaultdict[str, list[OrderUpdateDelta]] = defaultdict(list)
    for delta in order_deltas:
        plan_type = _resolve_plan_type(delta)
        if not plan_type:
            continue
        grouped_deltas[plan_type].append(delta)

    for plan_type, grouped in grouped_deltas.items():
        plan_type_module = get_plan_type_module(plan_type)
        if plan_type_module is None:
            continue
        partial = plan_type_module.apply_order_update(ctx, grouped, extension_context)
        result.instances.extend(partial.instances or [])
        merge_bundle_map(result.bundle_by_order_id, partial.bundle_by_order_id or {})

        for action in partial.post_flush_actions or []:
            result.post_flush_actions.append(
                wrap_post_flush_action(
                    action,
                    after=lambda partial=partial, result=result: merge_bundle_map(
                        result.bundle_by_order_id,
                        partial.bundle_by_order_id or {},
                    ),
                )
            )

    return result
