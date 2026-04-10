from Delivery_app_BK.models import CaseChat


def serialize_driver_case_chat_command_delta(instance: CaseChat):
    return {
        "id": instance.id,
        "client_id": instance.client_id,
        "message": instance.message,
        "order_case_id": instance.order_case_id,
        "creation_date": instance.creation_date.isoformat() if instance.creation_date else None,
    }
