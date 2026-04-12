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

ROUTE_PLAN_WORKFLOW_TYPE = "route_plan"
DEFAULT_ROUTE_PLAN_ORDER_OBJECTIVE = "local_delivery"


def normalize_order_plan_objective(value: str | None) -> str | None:
    if value is None:
        return None
    return ORDER_PLAN_OBJECTIVE_ALIASES.get(value, value)


def resolve_order_plan_workspace(value: str | None) -> str | None:
    normalized = normalize_order_plan_objective(value)
    if normalized is None:
        return None
    return ORDER_PLAN_WORKSPACE_BY_OBJECTIVE.get(normalized, normalized)


def resolve_route_plan_workflow_type() -> str:
    return ROUTE_PLAN_WORKFLOW_TYPE


def resolve_effective_order_plan_objective(
    value: str | None,
    *,
    has_route_plan: bool = False,
    fallback: str | None = None,
) -> str | None:
    normalized = normalize_order_plan_objective(value)
    if normalized is not None:
        return normalized

    fallback_normalized = normalize_order_plan_objective(fallback)
    if fallback_normalized is not None:
        return fallback_normalized

    if has_route_plan:
        return DEFAULT_ROUTE_PLAN_ORDER_OBJECTIVE

    return None
