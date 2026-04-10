from __future__ import annotations

from typing import Any

from sqlalchemy.exc import InvalidRequestError

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import (
    Costumer,
    CostumerAddress,
    CostumerOperatingHours,
    CostumerPhone,
    Team,
    db,
)
from Delivery_app_BK.services.utils import require_team_id

from ...context import ServiceContext
from ..utils import extract_fields
from ...requests.costumer import parse_create_costumer_request
from ...queries.costumer.serialize_costumer import serialize_costumer


def create_costumer(ctx: ServiceContext):
    ctx.set_relationship_map({"team_id": Team})
    create_requests = [parse_create_costumer_request(fields) for fields in extract_fields(ctx)]
    created_instances: list[Costumer] = []
    team_id = require_team_id(ctx)

    def _apply() -> None:
        for create_request in create_requests:
            scalar = create_request.fields
            costumer = Costumer(
                team_id=team_id,
                client_id=scalar.get("client_id"),
                first_name=scalar.get("first_name"),
                last_name=scalar.get("last_name"),
                email=scalar.get("email"),
                external_source=scalar.get("external_source"),
                external_costumer_id=scalar.get("external_costumer_id"),
            )
            db.session.add(costumer)
            db.session.flush()

            addresses_payload = create_request.addresses
            phones_payload = create_request.phones

            addresses = _create_addresses(team_id, costumer.id, addresses_payload)
            phones = _create_phones(team_id, costumer.id, phones_payload)
            operating_hours = _create_operating_hours(
                team_id,
                costumer.id,
                create_request.operating_hours,
            )
            if addresses:
                db.session.add_all(addresses)
            if phones:
                db.session.add_all(phones)
            if operating_hours:
                db.session.add_all(operating_hours)
            db.session.flush()

            default_address_id = scalar.get("default_address_id")
            default_primary_phone_id = scalar.get("default_primary_phone_id")
            default_secondary_phone_id = scalar.get("default_secondary_phone_id")

            flagged_address_id = _resolve_default_address_from_flags(
                addresses_payload,
                addresses,
            )
            flagged_primary_phone_id, flagged_secondary_phone_id = _resolve_default_phone_ids_from_flags(
                phones_payload,
                phones,
            )

            if default_address_id is not None and flagged_address_id is not None:
                raise ValidationFailed(
                    "Provide either default_address_id or addresses[].is_default, not both"
                )
            if default_primary_phone_id is not None and flagged_primary_phone_id is not None:
                raise ValidationFailed(
                    "Provide either default_primary_phone_id or phones[].is_default_primary, not both"
                )
            if default_secondary_phone_id is not None and flagged_secondary_phone_id is not None:
                raise ValidationFailed(
                    "Provide either default_secondary_phone_id or phones[].is_default_secondary, not both"
                )

            if default_address_id is not None:
                _validate_address_ownership(costumer, int(default_address_id))
                costumer.default_address_id = int(default_address_id)
            elif flagged_address_id is not None:
                _validate_address_ownership(costumer, int(flagged_address_id))
                costumer.default_address_id = int(flagged_address_id)
            if default_primary_phone_id is not None:
                _validate_phone_ownership(costumer, int(default_primary_phone_id))
                costumer.default_primary_phone_id = int(default_primary_phone_id)
            elif flagged_primary_phone_id is not None:
                _validate_phone_ownership(costumer, int(flagged_primary_phone_id))
                costumer.default_primary_phone_id = int(flagged_primary_phone_id)
            if default_secondary_phone_id is not None:
                _validate_phone_ownership(costumer, int(default_secondary_phone_id))
                costumer.default_secondary_phone_id = int(default_secondary_phone_id)
            elif flagged_secondary_phone_id is not None:
                _validate_phone_ownership(costumer, int(flagged_secondary_phone_id))
                costumer.default_secondary_phone_id = int(flagged_secondary_phone_id)

            created_instances.append(costumer)

    try:
        with db.session.begin():
            _apply()
    except InvalidRequestError as exc:
        if "already begun" not in str(exc).lower():
            raise
        _apply()
        db.session.commit()

    return {
        "created": [{"costumer": serialize_costumer(instance)} for instance in created_instances]
    }


def _create_addresses(
    team_id: int,
    costumer_id: int,
    addresses_payload: list[dict[str, Any]],
) -> list[CostumerAddress]:
    addresses: list[CostumerAddress] = []
    for entry in addresses_payload:
        addresses.append(
            CostumerAddress(
                team_id=team_id,
                costumer_id=costumer_id,
                client_id=entry.get("client_id"),
                label=entry.get("label"),
                address=entry.get("address"),
            )
        )
    return addresses


def _create_phones(
    team_id: int,
    costumer_id: int,
    phones_payload: list[dict[str, Any]],
) -> list[CostumerPhone]:
    phones: list[CostumerPhone] = []
    for entry in phones_payload:
        phones.append(
            CostumerPhone(
                team_id=team_id,
                costumer_id=costumer_id,
                client_id=entry.get("client_id"),
                label=entry.get("label"),
                phone=entry.get("phone"),
                phone_type=entry.get("phone_type"),
            )
        )
    return phones


def _create_operating_hours(
    team_id: int,
    costumer_id: int,
    hours_payload: list[dict[str, Any]],
) -> list[CostumerOperatingHours]:
    return [
        CostumerOperatingHours(
            team_id=team_id,
            costumer_id=costumer_id,
            client_id=row.get("client_id"),
            weekday=row["weekday"],
            open_time=row["open_time"],
            close_time=row["close_time"],
            is_closed=row["is_closed"],
        )
        for row in hours_payload
    ]


def _validate_address_ownership(costumer: Costumer, address_id: int) -> None:
    address_ids = {address.id for address in (costumer.addresses or [])}
    if address_id not in address_ids:
        raise ValidationFailed(f"default_address_id '{address_id}' does not belong to costumer")


def _validate_phone_ownership(costumer: Costumer, phone_id: int) -> None:
    phone_ids = {phone.id for phone in (costumer.phones or [])}
    if phone_id not in phone_ids:
        raise ValidationFailed(f"default phone id '{phone_id}' does not belong to costumer")


def _resolve_default_address_from_flags(
    payload: list[dict[str, Any]],
    instances: list[CostumerAddress],
) -> int | None:
    flagged_indexes = [idx for idx, row in enumerate(payload) if bool(row.get("is_default"))]
    if len(flagged_indexes) > 1:
        raise ValidationFailed("Only one addresses[].is_default is allowed")
    if not flagged_indexes:
        return None
    selected = instances[flagged_indexes[0]]
    return selected.id


def _resolve_default_phone_ids_from_flags(
    payload: list[dict[str, Any]],
    instances: list[CostumerPhone],
) -> tuple[int | None, int | None]:
    primary_indexes: list[int] = []
    secondary_indexes: list[int] = []

    for idx, row in enumerate(payload):
        is_primary = bool(row.get("is_default_primary"))
        is_secondary = bool(row.get("is_default_secondary"))
        if is_primary and is_secondary:
            raise ValidationFailed(
                "A phone cannot be both is_default_primary and is_default_secondary"
            )
        if is_primary:
            primary_indexes.append(idx)
        if is_secondary:
            secondary_indexes.append(idx)

    if len(primary_indexes) > 1:
        raise ValidationFailed("Only one phones[].is_default_primary is allowed")
    if len(secondary_indexes) > 1:
        raise ValidationFailed("Only one phones[].is_default_secondary is allowed")

    primary_id = instances[primary_indexes[0]].id if primary_indexes else None
    secondary_id = instances[secondary_indexes[0]].id if secondary_indexes else None
    return primary_id, secondary_id
