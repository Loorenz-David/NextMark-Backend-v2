from .route_plan import (
    register_route_plan_event_handlers,
)
from .order import register_order_event_handlers
from Delivery_app_BK.services.infra.events.event_bus import EventBus


def register_plan_event_handlers(event_bus: EventBus) -> None:
    # Backward-compatible alias for existing imports.
    register_route_plan_event_handlers(event_bus)


__all__ = [
    "register_route_plan_event_handlers",
    "register_order_event_handlers",
    "register_plan_event_handlers",
]
