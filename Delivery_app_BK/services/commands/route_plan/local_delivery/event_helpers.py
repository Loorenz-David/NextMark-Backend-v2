"""Event creation helpers for local delivery plan, route solution, and route stop changes."""

from Delivery_app_BK.services.context import ServiceContext


def create_local_delivery_plan_event(
    ctx: ServiceContext,
    team_id: int,
    route_group_id: int,
    event_name: str,
    payload: dict | None = None,
) -> None:
    """
    Stub: Local delivery plan events are not currently persisted (table does not exist).
    """
    return None


def create_route_group_event(
    ctx: ServiceContext,
    team_id: int,
    route_group_id: int,
    event_name: str,
    payload: dict | None = None,
) -> None:
    """
    Canonical alias for route-group terminology.
    """
    return create_local_delivery_plan_event(
        ctx=ctx,
        team_id=team_id,
        route_group_id=route_group_id,
        event_name=event_name,
        payload=payload,
    )


def create_route_solution_event(
    ctx: ServiceContext,
    team_id: int,
    route_solution_id: int,
    event_name: str,
    payload: dict | None = None,
) -> None:
    """
    Stub: Route solution events are not currently persisted (table does not exist).
    """
    return None


def create_route_solution_stop_event(
    ctx: ServiceContext,
    team_id: int,
    route_solution_stop_id: int,
    event_name: str,
    payload: dict | None = None,
) -> None:
    """
    Stub: Route solution stop events are not currently persisted (table does not exist).
    """
    return None
