from Delivery_app_BK.services.infra.events.event_bus import EventBus
from Delivery_app_BK.services.infra.events.registry import (
    register_route_plan_event_handlers,
    register_order_event_handlers,
)


_event_bus = EventBus()
_registered = False


def get_event_bus() -> EventBus:
    global _registered
    if not _registered:
        register_order_event_handlers(_event_bus)
        register_route_plan_event_handlers(_event_bus)
        _registered = True
    return _event_bus
