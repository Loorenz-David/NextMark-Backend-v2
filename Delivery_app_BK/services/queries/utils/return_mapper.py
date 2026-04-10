from typing import List, Dict

from Delivery_app_BK.errors import ValidationFailed
from ...context import ServiceContext
from . import (
    build_ids_map,
    build_client_ids_map
)


def map_return_values(
        unpacked_instances: List[ Dict ],
        ctx: ServiceContext,
        table: str = ""
):
    
    if ctx.on_query_return == 'ids_map':
        return build_ids_map( unpacked_instances, ctx, table )

    elif ctx.on_query_return == 'client_ids_map' :
        return build_client_ids_map( unpacked_instances, ctx, table )

    elif ctx.on_query_return == 'list':
        return unpacked_instances

    else:
        return unpacked_instances

