from __future__ import annotations

from typing import Any

from Delivery_app_BK.models import Costumer


def serialize_costumer(instance: Costumer, include_order_count: bool = False) -> dict[str, Any]:
    default_address = None
    if instance.default_address_id:
        default_address = _find_address_by_id(instance, instance.default_address_id)

    default_primary_phone = None
    if instance.default_primary_phone_id:
        default_primary_phone = _find_phone_by_id(instance, instance.default_primary_phone_id)

    default_secondary_phone = None
    if instance.default_secondary_phone_id:
        default_secondary_phone = _find_phone_by_id(instance, instance.default_secondary_phone_id)

    serialized = {
        "id": instance.id,
        "client_id": instance.client_id,
        "first_name": instance.first_name,
        "last_name": instance.last_name,
        "email": instance.email,
        "default_address": default_address,
        "default_primary_phone": default_primary_phone,
        "default_secondary_phone": default_secondary_phone,
        "operating_hours": [
            {
                "client_id": hours.client_id,
                "weekday": hours.weekday,
                "open_time": None if hours.is_closed else hours.open_time,
                "close_time": None if hours.is_closed else hours.close_time,
                "is_closed": bool(hours.is_closed),
            }
            for hours in sorted(instance.operating_hours or [], key=lambda row: row.weekday)
        ],
    }

    if include_order_count:
        active_order_count = getattr(instance, "active_order_count", None)
        if active_order_count is None:
            orders = getattr(instance, "orders", None) or []
            active_order_count = sum(1 for order in orders if getattr(order, "archive_at", None) is None)
        serialized["active_order_count"] = int(active_order_count)

    return serialized


def serialize_costumers(
    instances: list[Costumer],
    include_order_count: bool = False,
) -> list[dict[str, Any]]:
    return [
        serialize_costumer(instance, include_order_count=include_order_count)
        for instance in instances
    ]


def _find_address_by_id(instance: Costumer, address_id: int) -> dict[str, Any] | None:
    for address in instance.addresses or []:
        if address.id == address_id:
            return {
                "id": address.id,
                "client_id": address.client_id,
                "label": address.label,
                "address": address.address,
            }
    return None


def _find_phone_by_id(instance: Costumer, phone_id: int) -> dict[str, Any] | None:
    for phone in instance.phones or []:
        if phone.id == phone_id:
            return {
                "id": phone.id,
                "client_id": phone.client_id,
                "label": phone.label,
                "phone": phone.phone,
                "phone_type": phone.phone_type,
            }
    return None
