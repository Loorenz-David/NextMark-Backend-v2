from Delivery_app_BK.models import OrderCase


def serialize_driver_order_case_command_delta(instance: OrderCase):
    return {
        "id": instance.id,
        "client_id": instance.client_id,
        "state": instance.state,
        "order_id": instance.order_id,
        "creation_date": instance.creation_date.isoformat() if instance.creation_date else None,
    }
