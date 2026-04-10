from __future__ import annotations

from collections import defaultdict

from ....context import ServiceContext
from ..extensions import wrap_post_flush_action
from .registry import resolve_delete_extension_handler
from .types import OrderDeleteDelta, OrderDeleteExtensionContext, OrderDeleteExtensionResult


def apply_order_delete_extensions(
    ctx: ServiceContext,
    delete_deltas: list[OrderDeleteDelta],
    extension_context: OrderDeleteExtensionContext,
) -> OrderDeleteExtensionResult:
    result = OrderDeleteExtensionResult()
    if not delete_deltas:
        return result

    grouped: defaultdict[str, list[OrderDeleteDelta]] = defaultdict(list)
    for delta in delete_deltas:
        plan_type = getattr(delta.delivery_plan, "plan_type", None)
        if not plan_type:
            continue
        grouped[plan_type].append(delta)

    for plan_type, grouped_deltas in grouped.items():
        handler = resolve_delete_extension_handler(plan_type)
        if not handler:
            continue
        partial = handler(ctx, grouped_deltas, extension_context)
        result.instances.extend(partial.instances or [])
        result.updated_bundles.extend(partial.updated_bundles or [])

        for action in partial.post_flush_actions or []:
            result.post_flush_actions.append(
                wrap_post_flush_action(
                    action,
                    after=lambda partial=partial, result=result: result.updated_bundles.extend(
                        partial.updated_bundles or []
                    ),
                )
            )

    return result
