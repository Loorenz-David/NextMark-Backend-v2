ORDER_PLAN_OBJECTIVES = {
    "local_delivery",
    "international_shipping",
    "store_pickup",
}

ORDER_PLAN_OBJECTIVE_ALIASES = {
    "route_operation": "local_delivery",
    "route_operations": "local_delivery",
}

ORDER_PLAN_WORKSPACE_BY_OBJECTIVE = {
    "local_delivery": "route_operations",
    "international_shipping": "international_shipping",
    "store_pickup": "store_pickup",
}


def normalize_order_plan_objective(value: str | None) -> str | None:
    if value is None:
        return None
    return ORDER_PLAN_OBJECTIVE_ALIASES.get(value, value)


def resolve_order_plan_workspace(value: str | None) -> str | None:
    normalized = normalize_order_plan_objective(value)
    if normalized is None:
        return None
    return ORDER_PLAN_WORKSPACE_BY_OBJECTIVE.get(normalized, normalized)
