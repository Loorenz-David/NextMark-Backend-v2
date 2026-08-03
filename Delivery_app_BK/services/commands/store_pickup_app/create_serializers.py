from Delivery_app_BK.models import RoutePlan, StorePickupPlan
from Delivery_app_BK.services.commands.route_plan.create_serializers import (
    serialize_created_route_plan,
)


def serialize_created_store_pickup_plan(instance: StorePickupPlan) -> dict:
    return {
        "id": instance.id,
        "client_id": instance.client_id,
        "route_plan_id": instance.route_plan_id,
        "pickup_location": instance.pickup_location,
        "assigned_user_id": instance.assigned_user_id,
    }


def serialize_created_store_pickup_bundle(
    route_plan: RoutePlan,
    store_pickup_plan: StorePickupPlan,
) -> dict:
    return {
        "route_plan": serialize_created_route_plan(route_plan),
        "store_pickup_plan": serialize_created_store_pickup_plan(store_pickup_plan),
    }
