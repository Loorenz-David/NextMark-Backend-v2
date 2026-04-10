from typing import List

from Delivery_app_BK.models import RoutePlanState
from Delivery_app_BK.services.context import ServiceContext

from ..data import PLAN_STATE_SEEDS
from ..helpers import ensure_client_id, get_or_create


def seed_plan_states(ctx: ServiceContext) -> List[RoutePlanState]:
    states: List[RoutePlanState] = []

    for payload in PLAN_STATE_SEEDS:
        fields = ensure_client_id(dict(payload))
        lookup = {"name": fields["name"], "index": fields["index"]}
        instance, _ = get_or_create(ctx, RoutePlanState, lookup, fields)
        states.append(instance)

    return states
