from Delivery_app_BK.models import RouteGroup
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.route_operations.plan.route_group_zone_snapshot import (
    normalize_route_group_zone_snapshot,
)
from Delivery_app_BK.services.queries.utils import map_return_values


def _serialize_route_group_item(instance: RouteGroup) -> dict:
    state = getattr(instance, "state", None)
    raw_snapshot = getattr(instance, "zone_geometry_snapshot", None)
    zone_snapshot = normalize_route_group_zone_snapshot(raw_snapshot)
    return {
        "id": instance.id,
        "client_id": instance.client_id,
        "zone_id": getattr(instance, "zone_id", None),
        "zone_snapshot": zone_snapshot,
        "template_snapshot": getattr(instance, "template_snapshot", None),
        "updated_at": instance.updated_at.isoformat() if instance.updated_at else None,
        "route_plan_id": instance.route_plan_id,
        "state_id": state.id if state is not None else None,
        "total_orders": instance.total_orders,
        "total_item_count": instance.total_item_count,
        "total_volume_cm3": instance.total_volume_cm3,
        "total_weight_grams": instance.total_weight_g,
        "order_state_counts": instance.order_state_counts,
        "item_type_counts": instance.item_type_counts,
    }


def serialize_route_group(instance: RouteGroup, ctx: ServiceContext):
    unpacked_instances = [_serialize_route_group_item(instance)]
    mapped_instances = map_return_values(unpacked_instances, ctx, "route_group")
    return mapped_instances[0] if isinstance(mapped_instances, list) else mapped_instances


def serialize_route_groups(instances: list[RouteGroup], ctx: ServiceContext):
    unpacked_instances = [_serialize_route_group_item(instance) for instance in instances]

    return map_return_values(unpacked_instances, ctx, "route_group")
