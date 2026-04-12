from __future__ import annotations

from collections import defaultdict

from Delivery_app_BK.services.domain.order.plan_objective_labels import (
    resolve_effective_order_plan_objective,
)
from ....context import ServiceContext
from ..extensions import merge_bundle_map, wrap_post_flush_action
from .registry import resolve_update_extension_handler
from .types import OrderUpdateDelta, OrderUpdateExtensionContext, OrderUpdateExtensionResult


def _resolve_plan_type(delta: OrderUpdateDelta) -> str | None:
    delivery_plan = delta.delivery_plan
    order = delta.order_instance
    return resolve_effective_order_plan_objective(
        getattr(order, "order_plan_objective", None),
        has_route_plan=delivery_plan is not None,
    )


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
        handler = resolve_update_extension_handler(plan_type)
        if not handler:
            continue
        partial = handler(ctx, grouped, extension_context)
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
