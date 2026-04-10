from sqlalchemy.orm import selectinload

from Delivery_app_BK.models import RouteGroup, RouteSolution, db
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.drivers.serialize_active_routes import (
    serialize_active_routes,
)
from Delivery_app_BK.services.utils import require_team_id


def list_active_routes(ctx: ServiceContext):
    team_id = require_team_id(ctx)

    route_solutions = (
        db.session.query(RouteSolution)
        .options(
            selectinload(RouteSolution.route_group).selectinload(
                RouteGroup.route_plan
            ),
            selectinload(RouteSolution.stops),
        )
        .filter(
            RouteSolution.team_id == team_id,
            RouteSolution.driver_id == ctx.user_id,
            RouteSolution.is_selected.is_(True),
        )
        .order_by(RouteSolution.created_at.desc(), RouteSolution.id.desc())
        .all()
    )
    print(route_solutions)
    return {
        "routes": serialize_active_routes(
            instances=route_solutions,
            ctx=ctx,
        ),
    }
