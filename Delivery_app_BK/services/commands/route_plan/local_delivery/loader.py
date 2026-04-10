from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import RoutePlan, RouteGroup, RouteSolution
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.get_instance import get_instance
from Delivery_app_BK.services.requests.route_plan.plan.local_delivery.update_settings import (
    RouteGroupSettingsRequest,
)


def load_local_delivery_settings_entities(
    ctx: ServiceContext,
    request: RouteGroupSettingsRequest,
) -> tuple[RouteGroup, RoutePlan, RouteSolution]:
    route_group: RouteGroup = get_instance(
        ctx=ctx,
        model=RouteGroup,
        value=request.route_group_id,
    )

    route_plan: RoutePlan | None = route_group.route_plan
    if not route_plan:
        raise ValidationFailed("Route group has no route plan.")

    route_solution: RouteSolution = get_instance(
        ctx=ctx,
        model=RouteSolution,
        value=request.route_solution.route_solution_id,
    )

    if route_solution.route_group_id != route_group.id:
        raise ValidationFailed("Route solution does not belong to route group.")

    return route_group, route_plan, route_solution


def load_route_group_settings_entities(
    ctx: ServiceContext,
    request: RouteGroupSettingsRequest,
) -> tuple[RouteGroup, RoutePlan, RouteSolution]:
    return load_local_delivery_settings_entities(ctx, request)
