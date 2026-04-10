from ...context import ServiceContext
from ..order_states.list_order_states import list_order_states


def get_driver_bootstrap(ctx: ServiceContext):
    ctx.query_params = {}

    return {
        "order_states": list_order_states(ctx)["order_states"],
        "route_timing": {
            "arrival_range_meters": 75,
            "visible_location_poll_interval_seconds": 20,
        },
    }
