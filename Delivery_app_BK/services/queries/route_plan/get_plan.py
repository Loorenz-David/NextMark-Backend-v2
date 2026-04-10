from sqlalchemy.orm import selectinload

from Delivery_app_BK.models import RouteGroup, RoutePlan, db
from Delivery_app_BK.errors import NotFound

from ...context import ServiceContext
from .serialize_plan import serialize_plans


def get_plan(plan_id: int, ctx: ServiceContext):
    query = db.session.query(RoutePlan).options(
        selectinload(RoutePlan.route_groups).selectinload(RouteGroup.state)
    )
    if ctx.team_id:
        query = query.filter(RoutePlan.team_id == ctx.team_id)
    found_plan = query.filter(RoutePlan.id == plan_id).one_or_none()

    if not found_plan:
        raise NotFound(f"Route plan with id: {plan_id} does not exist.")

    serialized = serialize_plans(
        instances=[found_plan],
        ctx=ctx,
        include_route_groups_summary=True,
    )

    return {
        "route_plan": serialized[0] if isinstance(serialized, list) else serialized
    }
