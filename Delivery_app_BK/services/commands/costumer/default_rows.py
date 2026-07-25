from __future__ import annotations

from typing import Any

from Delivery_app_BK.models import Costumer, CostumerAddress, CostumerPhone, db
from Delivery_app_BK.services.commands.utils.client_id_generator import generate_client_id


def upsert_default_address(costumer: Costumer, address: dict[str, Any], team_id: int) -> None:
    """Update the costumer's default address in place, or create one as default."""
    default_id = costumer.default_address_id
    if default_id is not None:
        for row in costumer.addresses or []:
            if row.id == default_id:
                row.address = address
                return

    new_row = CostumerAddress(
        team_id=team_id,
        costumer_id=costumer.id,
        client_id=generate_client_id("costumer_address"),
        address=address,
    )
    costumer.addresses.append(new_row)
    db.session.flush()
    costumer.default_address_id = new_row.id


def upsert_default_phone(
    costumer: Costumer,
    phone: dict[str, str] | None,
    team_id: int,
    *,
    slot: str,
) -> None:
    """Update the costumer's default primary/secondary phone, or create one."""
    if not phone:
        return

    attr = "default_primary_phone_id" if slot == "primary" else "default_secondary_phone_id"
    default_id = getattr(costumer, attr)
    if default_id is not None:
        for row in costumer.phones or []:
            if row.id == default_id:
                row.phone = phone
                return

    new_row = CostumerPhone(
        team_id=team_id,
        costumer_id=costumer.id,
        client_id=generate_client_id("costumer_phone"),
        phone=phone,
    )
    costumer.phones.append(new_row)
    db.session.flush()
    setattr(costumer, attr, new_row.id)
