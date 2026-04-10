"""Zone assignment hooks for order create/update flows."""

from typing import List, Optional
from Delivery_app_BK.models import Order
from Delivery_app_BK.zones.services import upsert_order_zone_assignment


def assign_zones_for_created_orders(order_instances: List[Order]) -> None:
    """
    Post-flush hook to assign zones to newly created orders.
    
    Called after order instances are persisted, triggers zone assignment
    for each order based on its client_address.
    
    Args:
        order_instances: List of Order instances that were just created
    """
    for order in order_instances:
        if order.id and order.team_id:
            try:
                upsert_order_zone_assignment(
                    order_id=order.id,
                    team_id=order.team_id,
                    client_address=order.client_address,
                    user_specified_zone_id=None,  # New orders don't have user-specified zones
                )
            except Exception as e:
                # Log but don't fail the order creation if zone assignment fails
                # This allows orders to be created even if zones are not yet set up
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Zone assignment failed for order {order.id}: {str(e)}"
                )


def assign_zones_for_updated_orders(
    updated_orders: List[Order],
    address_changed_order_ids: Optional[set] = None,
) -> None:
    """
    Post-flush hook to reassign zones for orders with changed addresses.
    
    Called after order updates are persisted. Only triggers zone reassignment
    for orders where the client_address field was modified (not other fields).
    
    Args:
        updated_orders: List of Order instances that were just updated
        address_changed_order_ids: Set of order IDs where client_address changed (optional optimization)
    """
    for order in updated_orders:
        # Skip if address wasn't changed and we have tracking data
        if address_changed_order_ids is not None and order.id not in address_changed_order_ids:
            continue
        
        if order.id and order.team_id:
            try:
                upsert_order_zone_assignment(
                    order_id=order.id,
                    team_id=order.team_id,
                    client_address=order.client_address,
                    user_specified_zone_id=None,  # Updates don't change user overrides
                )
            except Exception as e:
                # Log but don't fail the order update if zone assignment fails
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Zone assignment failed for order {order.id} during update: {str(e)}"
                )
