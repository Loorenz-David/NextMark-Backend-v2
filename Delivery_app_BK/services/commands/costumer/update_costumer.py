from __future__ import annotations

from typing import Any

from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import selectinload

from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.models import (
    Costumer,
    CostumerAddress,
    CostumerOperatingHours,
    CostumerPhone,
    Team,
    db,
)
from Delivery_app_BK.services.utils import model_requires_team, require_team_id

from ...context import ServiceContext
from ...queries.costumer.serialize_costumer import serialize_costumer
from ...requests.costumer import parse_update_costumer_target_request
from ...requests.common.types import validate_int_list
from ...requests.costumer.common import validate_and_normalize_phone
from ..utils import extract_targets
from ..utils.client_id_generator import generate_client_id


SCALAR_MUTABLE_FIELDS = {
    "first_name",
    "last_name",
    "email",
    "external_source",
    "external_costumer_id",
    "default_address_id",
    "default_primary_phone_id",
    "default_secondary_phone_id",
}


def update_costumer(ctx: ServiceContext):
    ctx.set_relationship_map({"team_id": Team})
    targets = [parse_update_costumer_target_request(raw_target) for raw_target in extract_targets(ctx)]
    target_ids = [target.target_id for target in targets]
    team_id = require_team_id(ctx)

    query = db.session.query(Costumer).options(
        selectinload(Costumer.addresses),
        selectinload(Costumer.phones),
        selectinload(Costumer.operating_hours),
    )
    if model_requires_team(Costumer) and ctx.check_team_id:
        query = query.filter(Costumer.team_id == team_id)
    loaded = query.filter(Costumer.id.in_(target_ids)).all()
    by_id = {instance.id: instance for instance in loaded}

    missing = [target_id for target_id in target_ids if target_id not in by_id]
    if missing:
        raise NotFound(f"Costumers not found: {missing}")

    updated_instances: list[Costumer] = []

    def _apply() -> None:
        for target in targets:
            target_id = target.target_id
            fields = target.fields

            instance = by_id[target_id]
            if not instance.client_id:
                instance.client_id = generate_client_id("costumer")
            scalar_fields = {k: fields[k] for k in SCALAR_MUTABLE_FIELDS if k in fields}

            for key, value in scalar_fields.items():
                setattr(instance, key, value)

            flagged_default_address_id = _apply_address_mutations(instance, fields, team_id)
            flagged_default_primary_phone_id, flagged_default_secondary_phone_id = _apply_phone_mutations(
                instance,
                fields,
                team_id,
            )
            _apply_operating_hours_mutations(instance, fields, team_id)

            _apply_default_fields(
                instance,
                fields,
                flagged_default_address_id=flagged_default_address_id,
                flagged_default_primary_phone_id=flagged_default_primary_phone_id,
                flagged_default_secondary_phone_id=flagged_default_secondary_phone_id,
            )
            updated_instances.append(instance)

        db.session.flush()

    try:
        with db.session.begin():
            _apply()
    except InvalidRequestError as exc:
        if "already begun" not in str(exc).lower():
            raise
        _apply()
        db.session.commit()

    return {
        "updated": [{"costumer": serialize_costumer(instance)} for instance in updated_instances]
    }


def _apply_address_mutations(
    instance: Costumer,
    fields: dict[str, Any],
    team_id: int,
) -> int | None:
    delete_ids = validate_int_list(fields.get("delete_address_ids"), field="delete_address_ids")
    addresses_by_id = {address.id: address for address in (instance.addresses or [])}
    deleted_ids: set[int] = set()
    flagged_default_rows: list[CostumerAddress] = []

    for address_id in delete_ids:
        address = addresses_by_id.get(address_id)
        if not address:
            raise ValidationFailed(f"Address '{address_id}' does not belong to costumer '{instance.id}'")
        if instance.default_address_id == address_id:
            instance.default_address_id = None
        db.session.delete(address)
        if instance.addresses and address in instance.addresses:
            instance.addresses.remove(address)
        deleted_ids.add(address_id)

    if "addresses" not in fields:
        return None

    addresses_payload = fields.get("addresses")
    if not isinstance(addresses_payload, list):
        raise ValidationFailed("addresses must be a list")

    for entry in addresses_payload:
        if not isinstance(entry, dict):
            raise ValidationFailed("addresses entries must be objects")
        address_id = entry.get("id")
        if address_id is None:
            created = CostumerAddress(
                team_id=team_id,
                costumer_id=instance.id,
                client_id=entry.get("client_id") or generate_client_id("costumer_address"),
                label=entry.get("label"),
                address=entry.get("address"),
            )
            instance.addresses.append(created)
            if bool(entry.get("is_default")):
                flagged_default_rows.append(created)
            continue

        if not isinstance(address_id, int):
            raise ValidationFailed("addresses.id must be an integer")
        if address_id in deleted_ids:
            raise ValidationFailed(f"Address '{address_id}' cannot be updated after deletion")
        existing = addresses_by_id.get(address_id)
        if not existing:
            raise ValidationFailed(
                f"Address '{address_id}' does not belong to costumer '{instance.id}'"
            )
        if "label" in entry:
            existing.label = entry.get("label")
        if "address" in entry:
            existing.address = entry.get("address")
        if "client_id" in entry and entry.get("client_id"):
            existing.client_id = entry.get("client_id")
        elif not existing.client_id:
            existing.client_id = generate_client_id("costumer_address")
        if bool(entry.get("is_default")):
            flagged_default_rows.append(existing)

    if len(flagged_default_rows) > 1:
        raise ValidationFailed("Only one addresses[].is_default is allowed")
    if flagged_default_rows:
        if flagged_default_rows[0].id is None:
            db.session.flush()
        return flagged_default_rows[0].id
    return None


def _apply_phone_mutations(
    instance: Costumer,
    fields: dict[str, Any],
    team_id: int,
) -> tuple[int | None, int | None]:
    delete_ids = validate_int_list(fields.get("delete_phone_ids"), field="delete_phone_ids")
    phones_by_id = {phone.id: phone for phone in (instance.phones or [])}
    deleted_ids: set[int] = set()
    flagged_primary_rows: list[CostumerPhone] = []
    flagged_secondary_rows: list[CostumerPhone] = []

    for phone_id in delete_ids:
        phone = phones_by_id.get(phone_id)
        if not phone:
            raise ValidationFailed(f"Phone '{phone_id}' does not belong to costumer '{instance.id}'")
        if instance.default_primary_phone_id == phone_id:
            instance.default_primary_phone_id = None
        if instance.default_secondary_phone_id == phone_id:
            instance.default_secondary_phone_id = None
        db.session.delete(phone)
        if instance.phones and phone in instance.phones:
            instance.phones.remove(phone)
        deleted_ids.add(phone_id)

    if "phones" not in fields:
        return None, None

    phones_payload = fields.get("phones")
    if not isinstance(phones_payload, list):
        raise ValidationFailed("phones must be a list")

    for entry in phones_payload:
        if not isinstance(entry, dict):
            raise ValidationFailed("phones entries must be objects")
        phone_id = entry.get("id")
        if phone_id is None:
            is_primary = bool(entry.get("is_default_primary"))
            is_secondary = bool(entry.get("is_default_secondary"))
            if is_primary and is_secondary:
                raise ValidationFailed(
                    "A phone cannot be both is_default_primary and is_default_secondary"
                )
            created = CostumerPhone(
                team_id=team_id,
                costumer_id=instance.id,
                client_id=entry.get("client_id") or generate_client_id("costumer_phone"),
                label=entry.get("label"),
                phone=validate_and_normalize_phone(entry.get("phone")),
                phone_type=entry.get("phone_type"),
            )
            instance.phones.append(created)
            if is_primary:
                flagged_primary_rows.append(created)
            if is_secondary:
                flagged_secondary_rows.append(created)
            continue

        if not isinstance(phone_id, int):
            raise ValidationFailed("phones.id must be an integer")
        if phone_id in deleted_ids:
            raise ValidationFailed(f"Phone '{phone_id}' cannot be updated after deletion")
        existing = phones_by_id.get(phone_id)
        if not existing:
            raise ValidationFailed(f"Phone '{phone_id}' does not belong to costumer '{instance.id}'")
        if "label" in entry:
            existing.label = entry.get("label")
        if "phone" in entry:
            existing.phone = validate_and_normalize_phone(entry.get("phone"))
        if "phone_type" in entry:
            existing.phone_type = entry.get("phone_type")
        if "client_id" in entry and entry.get("client_id"):
            existing.client_id = entry.get("client_id")
        elif not existing.client_id:
            existing.client_id = generate_client_id("costumer_phone")
        is_primary = bool(entry.get("is_default_primary"))
        is_secondary = bool(entry.get("is_default_secondary"))
        if is_primary and is_secondary:
            raise ValidationFailed(
                "A phone cannot be both is_default_primary and is_default_secondary"
            )
        if is_primary:
            flagged_primary_rows.append(existing)
        if is_secondary:
            flagged_secondary_rows.append(existing)

    if len(flagged_primary_rows) > 1:
        raise ValidationFailed("Only one phones[].is_default_primary is allowed")
    if len(flagged_secondary_rows) > 1:
        raise ValidationFailed("Only one phones[].is_default_secondary is allowed")

    primary_id = None
    secondary_id = None
    if flagged_primary_rows:
        if flagged_primary_rows[0].id is None:
            db.session.flush()
        primary_id = flagged_primary_rows[0].id
    if flagged_secondary_rows:
        if flagged_secondary_rows[0].id is None:
            db.session.flush()
        secondary_id = flagged_secondary_rows[0].id

    return primary_id, secondary_id


def _apply_operating_hours_mutations(instance: Costumer, fields: dict[str, Any], team_id: int) -> None:
    if fields.get("replace_operating_hours") is True:
        for existing in list(instance.operating_hours or []):
            db.session.delete(existing)
        instance.operating_hours = []
        # Ensure deleted weekday rows are removed before inserting replacements.
        db.session.flush()

    if "operating_hours" not in fields:
        return

    payload = fields.get("operating_hours")
    if not isinstance(payload, list):
        raise ValidationFailed("operating_hours must be a list")

    existing_by_weekday = {row.weekday: row for row in (instance.operating_hours or [])}

    for row in payload:
        existing = existing_by_weekday.get(row["weekday"])
        if existing:
            existing.open_time = row["open_time"]
            existing.close_time = row["close_time"]
            existing.is_closed = row["is_closed"]
            if row.get("client_id"):
                existing.client_id = row["client_id"]
            elif not existing.client_id:
                existing.client_id = generate_client_id("costumer_operating_hours")
            continue

        instance.operating_hours.append(
            CostumerOperatingHours(
                team_id=team_id,
                costumer_id=instance.id,
                client_id=row.get("client_id") or generate_client_id("costumer_operating_hours"),
                weekday=row["weekday"],
                open_time=row["open_time"],
                close_time=row["close_time"],
                is_closed=row["is_closed"],
            )
        )


def _apply_default_fields(
    instance: Costumer,
    fields: dict[str, Any],
    *,
    flagged_default_address_id: int | None,
    flagged_default_primary_phone_id: int | None,
    flagged_default_secondary_phone_id: int | None,
) -> None:
    if "default_address_id" in fields and flagged_default_address_id is not None:
        raise ValidationFailed(
            "Provide either default_address_id or addresses[].is_default, not both"
        )
    if "default_primary_phone_id" in fields and flagged_default_primary_phone_id is not None:
        raise ValidationFailed(
            "Provide either default_primary_phone_id or phones[].is_default_primary, not both"
        )
    if "default_secondary_phone_id" in fields and flagged_default_secondary_phone_id is not None:
        raise ValidationFailed(
            "Provide either default_secondary_phone_id or phones[].is_default_secondary, not both"
        )

    if "default_address_id" in fields:
        value = fields.get("default_address_id")
        if value is None:
            instance.default_address_id = None
        else:
            _ensure_address_owned(instance, int(value))
            instance.default_address_id = int(value)
    elif flagged_default_address_id is not None:
        _ensure_address_owned(instance, int(flagged_default_address_id))
        instance.default_address_id = int(flagged_default_address_id)

    if "default_primary_phone_id" in fields:
        value = fields.get("default_primary_phone_id")
        if value is None:
            instance.default_primary_phone_id = None
        else:
            _ensure_phone_owned(instance, int(value))
            instance.default_primary_phone_id = int(value)
    elif flagged_default_primary_phone_id is not None:
        _ensure_phone_owned(instance, int(flagged_default_primary_phone_id))
        instance.default_primary_phone_id = int(flagged_default_primary_phone_id)

    if "default_secondary_phone_id" in fields:
        value = fields.get("default_secondary_phone_id")
        if value is None:
            instance.default_secondary_phone_id = None
        else:
            _ensure_phone_owned(instance, int(value))
            instance.default_secondary_phone_id = int(value)
    elif flagged_default_secondary_phone_id is not None:
        _ensure_phone_owned(instance, int(flagged_default_secondary_phone_id))
        instance.default_secondary_phone_id = int(flagged_default_secondary_phone_id)


def _ensure_address_owned(instance: Costumer, address_id: int) -> None:
    owned_ids = {address.id for address in (instance.addresses or []) if address.id is not None}
    if address_id not in owned_ids:
        raise ValidationFailed(
            f"default_address_id '{address_id}' does not belong to costumer '{instance.id}'"
        )


def _ensure_phone_owned(instance: Costumer, phone_id: int) -> None:
    owned_ids = {phone.id for phone in (instance.phones or []) if phone.id is not None}
    if phone_id not in owned_ids:
        raise ValidationFailed(
            f"default phone id '{phone_id}' does not belong to costumer '{instance.id}'"
        )
