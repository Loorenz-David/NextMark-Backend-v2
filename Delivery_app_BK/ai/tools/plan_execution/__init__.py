from __future__ import annotations
from typing import Callable

from Delivery_app_BK.models import RoutePlan
from Delivery_app_BK.services.context import ServiceContext

from . import local_delivery_handler
from . import international_shipping_handler
from . import store_pickup_handler

# Registry: plan_type string → handler module.
# To support a new plan type: create a handler module and add one entry here.
_HANDLERS: dict[str, Callable[[ServiceContext, RoutePlan], dict]] = {
    "local_delivery": local_delivery_handler.get_execution_status,
    "international_shipping": international_shipping_handler.get_execution_status,
    "store_pickup": store_pickup_handler.get_execution_status,
}


def get_handler(plan_type: str) -> Callable[[ServiceContext, RoutePlan], dict] | None:
    return _HANDLERS.get(plan_type)
