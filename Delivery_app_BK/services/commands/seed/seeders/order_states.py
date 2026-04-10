from typing import List

from Delivery_app_BK.models import OrderState
from Delivery_app_BK.services.context import ServiceContext

from ..data import ORDER_STATE_SEEDS
from ..helpers import ensure_client_id, get_or_create


def seed_order_states(ctx: ServiceContext) -> List[OrderState]:
    states: List[OrderState] = []

    for payload in ORDER_STATE_SEEDS:
        fields = ensure_client_id(dict(payload))
        lookup = {"name": fields["name"], "index": fields["index"]}
        instance, _ = get_or_create(ctx, OrderState, lookup, fields)
        states.append(instance)

    return states
