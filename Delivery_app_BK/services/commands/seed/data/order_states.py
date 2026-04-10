
from Delivery_app_BK.services.domain.order.order_states import OrderStateId, OrderState


ORDER_STATE_SEEDS = [
    {   
        "id": OrderStateId.DRAFT,
        "name": OrderState.DRAFT.value,
        "color": "#9CA3AF",
        "index": OrderStateId.DRAFT,
        "is_system": True,
    },
    {
        "id": OrderStateId.CONFIRMED,
        "name": OrderState.CONFIRMED.value,
        "color": "#6B7280",
        "index": OrderStateId.CONFIRMED,
        "is_system": True,
    },
    {
        "id": OrderStateId.PREPARING,
        "name": OrderState.PREPARING.value,
        "color": "#F59E0B",
        "index": OrderStateId.PREPARING,
        "is_system": True,
    },
    {
        "id": OrderStateId.READY,
        "name": OrderState.READY.value,
        "color": "#10B981",
        "index": OrderStateId.READY,
        "is_system": True,
    },
    {
        "id": OrderStateId.PROCESSING,
        "name": OrderState.PROCESSING.value,
        "color": "#4F46E5",
        "index": OrderStateId.PROCESSING,
        "is_system": True,
    },
    {
        "id": OrderStateId.COMPLETED,
        "name": OrderState.COMPLETED.value,
        "color": "#16A34A",
        "index": OrderStateId.COMPLETED,
        "is_system": True,
    },
    {
        "id": OrderStateId.CANCELLED,
        "name": OrderState.CANCELLED.value,
        "color": "#EF4444",
        "index": OrderStateId.CANCELLED,
        "is_system": True,
    },
    {
        "id": OrderStateId.FAIL,
        "name": OrderState.FAIL.value,
        "color": "#EF4444",
        "index": OrderStateId.FAIL,
        "is_system": True,
    },
]
