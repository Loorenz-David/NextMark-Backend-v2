from Delivery_app_BK.models import RouteGroup, RoutePlan


def _load_route_groups_by_ids(route_group_ids: set[int]) -> list[RouteGroup]:
    if not route_group_ids:
        return []
    return (
        RouteGroup.query.filter(RouteGroup.id.in_(route_group_ids))
        .order_by(RouteGroup.id.asc())
        .all()
    )


def _load_route_plans_by_ids(route_plan_ids: set[int]) -> list[RoutePlan]:
    if not route_plan_ids:
        return []
    return (
        RoutePlan.query.filter(RoutePlan.id.in_(route_plan_ids))
        .order_by(RoutePlan.id.asc())
        .all()
    )


def _serialize_route_group_state(route_group: RouteGroup) -> dict:
    return {
        "id": route_group.id,
        "client_id": route_group.client_id,
        "route_plan_id": route_group.route_plan_id,
        "state_id": route_group.state_id,
        "total_orders": route_group.total_orders,
        "order_state_counts": route_group.order_state_counts,
    }


def _serialize_route_plan_state(route_plan: RoutePlan) -> dict:
    return {
        "id": route_plan.id,
        "client_id": route_plan.client_id,
        "state_id": route_plan.state_id,
        "total_orders": route_plan.total_orders,
    }


def build_order_state_update_payload(changed_orders: list) -> dict:
    return build_state_update_payload(changed_orders=changed_orders)


def build_state_update_payload(
    *,
    changed_orders: list | None = None,
    route_groups: list | None = None,
    route_plans: list | None = None,
) -> dict:
    changed = list(changed_orders or [])
    route_group_ids: set[int] = set()
    route_plan_ids: set[int] = set()
    orders_payload: list[dict] = []

    for order in changed:
        route_group_id = getattr(order, "route_group_id", None)
        if route_group_id is None:
            route_group = getattr(order, "route_group", None)
            route_group_id = getattr(route_group, "id", None)

        route_plan_id = getattr(order, "route_plan_id", None)
        if route_plan_id is None:
            route_plan = getattr(order, "route_plan", None) or getattr(order, "delivery_plan", None)
            route_plan_id = getattr(route_plan, "id", None)

        if route_group_id is not None:
            route_group_ids.add(route_group_id)
        if route_plan_id is not None:
            route_plan_ids.add(route_plan_id)

        orders_payload.append(
            {
                "id": getattr(order, "id", None),
                "client_id": getattr(order, "client_id", None),
                "order_state_id": getattr(order, "order_state_id", None),
                "route_group_id": route_group_id,
                "route_plan_id": route_plan_id,
            }
        )

    explicit_route_groups = list(route_groups or [])
    for route_group in explicit_route_groups:
        route_group_id = getattr(route_group, "id", None)
        if route_group_id is not None:
            route_group_ids.add(route_group_id)

    explicit_route_plans = list(route_plans or [])
    for route_plan in explicit_route_plans:
        route_plan_id = getattr(route_plan, "id", None)
        if route_plan_id is not None:
            route_plan_ids.add(route_plan_id)

    loaded_route_groups = _load_route_groups_by_ids(route_group_ids)
    loaded_route_plans = _load_route_plans_by_ids(route_plan_ids)

    return {
        "orders": orders_payload,
        "route_groups": [_serialize_route_group_state(group) for group in loaded_route_groups],
        "route_plans": [_serialize_route_plan_state(plan) for plan in loaded_route_plans],
    }
