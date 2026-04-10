from .tools.plan_tools import (
    optimize_plan_tool,
    get_plan_summary_tool,
    list_plans_tool,
    create_plan_tool,
    get_plan_execution_status_tool,
    list_routes_tool,
)
from .tools.order_tools import (
    list_orders_tool,
    assign_orders_to_plan_tool,
    assign_orders_tool,
    update_order_state_tool,
    update_order_tool,
    create_order_tool,
)
from .tools.item_tools import search_item_types_tool, add_items_to_order_tool

TOOLS: dict[str, callable] = {
    "optimize_plan": optimize_plan_tool,
    "get_plan_summary": get_plan_summary_tool,
    "list_plans": list_plans_tool,
    "create_plan": create_plan_tool,
    "get_plan_execution_status": get_plan_execution_status_tool,
    "list_routes": list_routes_tool,
    "list_orders": list_orders_tool,
    "assign_orders_to_plan": assign_orders_to_plan_tool,
    "assign_orders": assign_orders_tool,
    "update_order_state": update_order_state_tool,
    "update_order": update_order_tool,
    "create_order": create_order_tool,
    "search_item_types": search_item_types_tool,
    "add_items_to_order": add_items_to_order_tool,
}
