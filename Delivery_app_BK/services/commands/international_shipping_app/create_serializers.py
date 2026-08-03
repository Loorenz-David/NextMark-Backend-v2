from Delivery_app_BK.models import InternationalShippingPlan, RoutePlan
from Delivery_app_BK.services.commands.route_plan.create_serializers import (
    serialize_created_route_plan,
)


def serialize_created_international_shipping_plan(
    instance: InternationalShippingPlan,
) -> dict:
    return {
        "id": instance.id,
        "client_id": instance.client_id,
        "route_plan_id": instance.route_plan_id,
        "carrier_name": instance.carrier_name,
    }


def serialize_created_international_shipping_bundle(
    route_plan: RoutePlan,
    international_shipping_plan: InternationalShippingPlan,
) -> dict:
    return {
        "route_plan": serialize_created_route_plan(route_plan),
        "international_shipping_plan": serialize_created_international_shipping_plan(
            international_shipping_plan
        ),
    }
