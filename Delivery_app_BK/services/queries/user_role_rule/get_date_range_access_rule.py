from Delivery_app_BK.models import DateRangeAccessRule
from Delivery_app_BK.errors import NotFound

from ...context import ServiceContext
from ..get_instance import get_instance
from .serialize_date_range_access_rules import serialize_date_range_access_rules


def get_date_range_access_rule(rule_id: int, ctx: ServiceContext):
    found_rule = get_instance(
        ctx=ctx,
        model=DateRangeAccessRule,
        value=rule_id,
    )

    if not found_rule:
        raise NotFound(
            f"Date range access rule with id: {rule_id} does not exist."
        )

    serialized = serialize_date_range_access_rules(
        instances=[found_rule],
        ctx=ctx,
    )

    return {
        "date_range_access_rule": (
            serialized[0] if isinstance(serialized, list) else serialized
        )
    }
