from Delivery_app_BK.models import OrderStateTransitionRule
from Delivery_app_BK.errors import NotFound

from ...context import ServiceContext
from ..get_instance import get_instance
from .serialize_order_state_transition_rules import (
    serialize_order_state_transition_rules,
)


def get_order_state_transition_rule(rule_id: int, ctx: ServiceContext):
    found_rule = get_instance(
        ctx=ctx,
        model=OrderStateTransitionRule,
        value=rule_id,
    )

    if not found_rule:
        raise NotFound(
            f"Order state transition rule with id: {rule_id} does not exist."
        )

    serialized = serialize_order_state_transition_rules(
        instances=[found_rule],
        ctx=ctx,
    )

    return {
        "order_state_transition_rule": (
            serialized[0] if isinstance(serialized, list) else serialized
        )
    }
