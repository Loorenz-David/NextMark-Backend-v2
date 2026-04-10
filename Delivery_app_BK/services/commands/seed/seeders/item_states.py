from typing import List

from Delivery_app_BK.models import ItemState
from Delivery_app_BK.services.context import ServiceContext

from ..data import ITEM_STATE_SEEDS
from ..helpers import ensure_client_id, get_or_create


def seed_item_states(ctx: ServiceContext) -> List[ItemState]:
    states: List[ItemState] = []

    for payload in ITEM_STATE_SEEDS:
        fields = ensure_client_id(dict(payload))
        lookup = {"name": fields["name"], "entry_point": fields["entry_point"]}
        instance, _ = get_or_create(ctx, ItemState, lookup, fields)
        states.append(instance)

    return states
