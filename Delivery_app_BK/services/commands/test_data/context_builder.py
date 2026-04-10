from __future__ import annotations

from Delivery_app_BK.services.context import ServiceContext


def build_ctx(
    identity: dict,
    incoming_data: dict,
    *,
    prevent_event_bus: bool = True,
    on_create_return: str = "map_ids_object",
) -> ServiceContext:
    """Build a ServiceContext for test data processors."""
    return ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
        prevent_event_bus=prevent_event_bus,
        on_create_return=on_create_return,
    )


__all__ = ["build_ctx"]
