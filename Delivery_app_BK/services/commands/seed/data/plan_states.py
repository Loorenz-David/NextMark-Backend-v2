from Delivery_app_BK.services.domain.route_operations.plan.plan_states import PlanStateId, PlanState

PLAN_STATE_SEEDS = [
    {
        "id": PlanStateId.OPEN,
        "name": PlanState.OPEN.value,
        "color": "#F59E0B",
        "index": 1,
        "is_system": True,
    },
    {
        "id": PlanStateId.READY,
        "name": PlanState.READY.value,
        "color": "#10B981",
        "index": 2,
        "is_system": True,
    },
    {
        "id": PlanStateId.PROCESSING,
        "name": PlanState.PROCESSING.value,
        "color": "#4F46E5",
        "index": 3,
        "is_system": True,
    },
    {
        "id": PlanStateId.COMPLETED,
        "name": PlanState.COMPLETED.value,
        "color": "#16A34A",
        "index": 4,
        "is_system": True,
    },
    {
        "id": PlanStateId.FAIL,
        "name": PlanState.FAIL.value,
        "color": "#EF4444",
        "index": 5,
        "is_system": True,
    },
]
