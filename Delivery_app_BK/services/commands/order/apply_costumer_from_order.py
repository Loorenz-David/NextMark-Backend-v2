from __future__ import annotations

from typing import Any

from Delivery_app_BK.models import Costumer, Order, db
from Delivery_app_BK.services.commands.costumer.default_rows import (
    upsert_default_address,
    upsert_default_phone,
)
from Delivery_app_BK.services.requests.costumer.common import (
    normalize_email,
    validate_and_normalize_phone,
)


CLIENT_FIELD_KEYS = {
    "client_first_name",
    "client_last_name",
    "client_email",
    "client_address",
    "client_primary_phone",
    "client_secondary_phone",
}


def apply_order_client_fields_to_costumer(
    order: Order,
    submitted_fields: dict[str, Any],
) -> Costumer | None:
    """Propagate the order's submitted client_* fields onto its linked Costumer.

    Only the client fields present in ``submitted_fields`` are pushed, so a PATCH
    that edited (say) only the email will not clobber the costumer's name or
    address. Scalars are set directly; the address and primary/secondary phones
    upsert the costumer's default rows. Empty scalars are ignored so a required
    name is never wiped, while ``client_email`` may be explicitly cleared.
    """
    costumer = getattr(order, "costumer", None)
    if costumer is None:
        return None

    if not CLIENT_FIELD_KEYS.intersection(submitted_fields.keys()):
        return None

    team_id = costumer.team_id

    if "client_first_name" in submitted_fields:
        first_name = _clean_str(order.client_first_name)
        if first_name:
            costumer.first_name = first_name

    if "client_last_name" in submitted_fields:
        last_name = _clean_str(order.client_last_name)
        if last_name:
            costumer.last_name = last_name

    if "client_email" in submitted_fields:
        costumer.email = normalize_email(order.client_email)

    if "client_address" in submitted_fields:
        address = order.client_address
        if isinstance(address, dict) and address:
            upsert_default_address(costumer, address, team_id)

    if "client_primary_phone" in submitted_fields:
        phone = order.client_primary_phone
        if isinstance(phone, dict) and phone:
            upsert_default_phone(
                costumer,
                validate_and_normalize_phone(phone),
                team_id,
                slot="primary",
            )

    if "client_secondary_phone" in submitted_fields:
        phone = order.client_secondary_phone
        if isinstance(phone, dict) and phone:
            upsert_default_phone(
                costumer,
                validate_and_normalize_phone(phone),
                team_id,
                slot="secondary",
            )

    db.session.add(costumer)
    return costumer


def _clean_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None
