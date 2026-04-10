from Delivery_app_BK.models import RoutePlan

from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.get_instance import get_instance
from .serialize_route_group import serialize_route_group


def get_route_group_plan_type(plan_id: int, ctx: ServiceContext):
    found_plan: RoutePlan = get_instance(
        ctx=ctx,
        model=RoutePlan,
        value=plan_id,
    )

    route_groups = list(found_plan.route_groups or [])

    route_group = route_groups[0] if route_groups else None
    serialized = serialize_route_group(route_group, ctx) if route_group else None

    return {
        "route_group_type": serialized,
    }
