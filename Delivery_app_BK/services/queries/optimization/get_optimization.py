from Delivery_app_BK.models import RouteSolution
from Delivery_app_BK.errors import NotFound

from ...context import ServiceContext
from ..get_instance import get_instance
from .serialize_optimizations import serialize_optimizations


def get_optimization(optimization_id: int, ctx: ServiceContext):
    found_optimization = get_instance(
        ctx=ctx,
        model=RouteSolution,
        value=optimization_id,
    )

    if not found_optimization:
        raise NotFound(f"Route optimization with id: {optimization_id} does not exist.")

    serialized = serialize_optimizations(
        instances=[found_optimization],
        ctx=ctx,
    )

    return {
        "optimization": serialized[0] if isinstance(serialized, list) else serialized
    }
