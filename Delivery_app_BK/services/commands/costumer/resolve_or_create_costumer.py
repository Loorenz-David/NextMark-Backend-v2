from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func

from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.models import Costumer, CostumerAddress, CostumerPhone, db
from Delivery_app_BK.services.utils import require_team_id

from ...context import ServiceContext
from ...requests.costumer.common import (
    normalize_email,
    normalized_phone_string,
    validate_and_normalize_phone,
)
from ..utils.client_id_generator import generate_client_id


@dataclass
class CostumerResolutionInput:
    costumer_id: int | None = None
    costumer_client_id: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    primary_phone: dict[str, Any] | None = None
    address: dict[str, Any] | None = None


@dataclass
class _NormalizedCostumerResolutionInput:
    costumer_id: int | None
    costumer_client_id: str | None
    first_name: str | None
    last_name: str | None
    normalized_email: str | None
    normalized_phone: dict[str, str] | None
    normalized_phone_key: str | None
    address: dict[str, Any] | None


def resolve_or_create_costumer(
    ctx: ServiceContext,
    first_name: str | None,
    last_name: str | None,
    email: str | None,
    primary_phone: dict[str, Any] | None,
    address: dict[str, Any] | None,
) -> Costumer:
    resolved = resolve_or_create_costumers(
        ctx,
        [
                CostumerResolutionInput(
                    costumer_id=None,
                    costumer_client_id=None,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    primary_phone=primary_phone,
                address=address,
            )
        ],
    )
    return resolved[0]


def resolve_or_create_costumers(
    ctx: ServiceContext,
    inputs: list[CostumerResolutionInput | dict[str, Any]],
) -> list[Costumer]:
    if not isinstance(inputs, list):
        raise ValidationFailed("Costumer resolver input must be a list.")
    if not inputs:
        return []

    team_id = require_team_id(ctx)
    normalized_inputs: list[_NormalizedCostumerResolutionInput] = []
    explicit_costumer_ids: list[int] = []
    hinted_costumer_client_ids: set[str] = set()
    unresolved_email_keys: set[str] = set()
    unresolved_phone_keys: set[str] = set()

    for raw_input in inputs:
        entry = _coerce_input(raw_input)
        if entry.costumer_id is not None and (
            isinstance(entry.costumer_id, bool) or not isinstance(entry.costumer_id, int)
        ):
            raise ValidationFailed("costumer_id must be an integer.")
        if entry.costumer_client_id is not None and not isinstance(entry.costumer_client_id, str):
            raise ValidationFailed("costumer.client_id must be a string.")

        normalized_client_id = (
            str(entry.costumer_client_id).strip() if entry.costumer_client_id is not None else ""
        )
        normalized_client_id = normalized_client_id or None
        normalized_phone = validate_and_normalize_phone(entry.primary_phone)
        normalized_phone_key = normalized_phone_string(normalized_phone)
        normalized_email = normalize_email(entry.email)

        normalized_entry = _NormalizedCostumerResolutionInput(
            costumer_id=entry.costumer_id,
            costumer_client_id=normalized_client_id,
            first_name=entry.first_name,
            last_name=entry.last_name,
            normalized_email=normalized_email,
            normalized_phone=normalized_phone,
            normalized_phone_key=normalized_phone_key,
            address=entry.address if isinstance(entry.address, dict) else None,
        )
        normalized_inputs.append(normalized_entry)

        if normalized_entry.costumer_id is not None:
            explicit_costumer_ids.append(normalized_entry.costumer_id)
        if normalized_entry.costumer_client_id:
            hinted_costumer_client_ids.add(normalized_entry.costumer_client_id)
        if normalized_entry.normalized_email:
            unresolved_email_keys.add(normalized_entry.normalized_email)
        if normalized_entry.normalized_phone_key:
            unresolved_phone_keys.add(normalized_entry.normalized_phone_key)

    costumer_by_id = _load_costumers_by_ids(team_id, explicit_costumer_ids)
    costumer_by_client_id = _load_costumers_by_client_ids(team_id, hinted_costumer_client_ids)
    costumer_by_email = _load_costumers_by_email(team_id, unresolved_email_keys)
    costumer_by_phone = _load_costumers_by_phone(team_id, unresolved_phone_keys)
    resolved_costumers: list[Costumer] = []

    for entry in normalized_inputs:
        resolved: Costumer | None = None
        if entry.costumer_id is not None:
            resolved = costumer_by_id[entry.costumer_id]
            if entry.costumer_client_id:
                by_client = costumer_by_client_id.get(entry.costumer_client_id)
                if by_client and by_client.id != resolved.id:
                    raise ValidationFailed(
                        "costumer_id and costumer.client_id point to different costumers."
                    )
        elif entry.costumer_client_id:
            resolved = costumer_by_client_id.get(entry.costumer_client_id)

        if not resolved and entry.normalized_email:
            resolved = costumer_by_email.get(entry.normalized_email)

        if not resolved and entry.normalized_phone_key:
            resolved = costumer_by_phone.get(entry.normalized_phone_key)

        if not resolved:
            resolved = _create_costumer_from_snapshot(
                team_id=team_id,
                first_name=entry.first_name,
                last_name=entry.last_name,
                preferred_client_id=entry.costumer_client_id,
                normalized_email=entry.normalized_email,
                normalized_phone=entry.normalized_phone,
                address=entry.address,
            )

        if entry.costumer_client_id and entry.costumer_client_id not in costumer_by_client_id:
            costumer_by_client_id[entry.costumer_client_id] = resolved
        if entry.normalized_email and entry.normalized_email not in costumer_by_email:
            costumer_by_email[entry.normalized_email] = resolved
        if entry.normalized_phone_key and entry.normalized_phone_key not in costumer_by_phone:
            costumer_by_phone[entry.normalized_phone_key] = resolved

        resolved_costumers.append(resolved)

    return resolved_costumers


def _create_costumer_from_snapshot(
    *,
    team_id: int,
    first_name: str | None,
    last_name: str | None,
    preferred_client_id: str | None,
    normalized_email: str | None,
    normalized_phone: dict[str, str] | None,
    address: dict[str, Any] | None,
) -> Costumer:
    created_costumer = Costumer(
        team_id=team_id,
        client_id=preferred_client_id or generate_client_id("costumer"),
        first_name=first_name or "",
        last_name=last_name or "",
        email=normalized_email,
    )
    db.session.add(created_costumer)
    db.session.flush()

    if address is not None:
        address_row = CostumerAddress(
            team_id=team_id,
            costumer_id=created_costumer.id,
            client_id=generate_client_id("costumer_address"),
            label=address.get("label"),
            address=address,
        )
        db.session.add(address_row)
        db.session.flush()
        created_costumer.default_address_id = address_row.id

    if normalized_phone is not None:
        phone_row = CostumerPhone(
            team_id=team_id,
            costumer_id=created_costumer.id,
            client_id=generate_client_id("costumer_phone"),
            phone=normalized_phone,
        )
        db.session.add(phone_row)
        db.session.flush()
        created_costumer.default_primary_phone_id = phone_row.id

    return created_costumer



def _coerce_input(
    raw_input: CostumerResolutionInput | dict[str, Any],
) -> CostumerResolutionInput:
    if isinstance(raw_input, CostumerResolutionInput):
        return raw_input
    if isinstance(raw_input, dict):
        return CostumerResolutionInput(
            costumer_id=raw_input.get("costumer_id"),
            costumer_client_id=raw_input.get("costumer_client_id") or raw_input.get("client_id"),
            first_name=raw_input.get("first_name"),
            last_name=raw_input.get("last_name"),
            email=raw_input.get("email"),
            primary_phone=raw_input.get("primary_phone"),
            address=raw_input.get("address"),
        )
    raise ValidationFailed("Each costumer resolver input must be an object.")


def _load_costumers_by_ids(
    team_id: int,
    costumer_ids: list[int],
) -> dict[int, Costumer]:
    deduped_ids = list(dict.fromkeys(costumer_ids))
    if not deduped_ids:
        return {}

    query = (
        db.session.query(Costumer)
        .filter(
            Costumer.team_id == team_id,
            Costumer.id.in_(deduped_ids),
        )
    )
    instances = query.all()
    by_id = {instance.id: instance for instance in instances}
    missing_ids = [costumer_id for costumer_id in deduped_ids if costumer_id not in by_id]
    if missing_ids:
        raise NotFound(f"Costumers not found: {missing_ids}")

    return by_id


def _load_costumers_by_client_ids(
    team_id: int,
    costumer_client_ids: set[str],
) -> dict[str, Costumer]:
    deduped_client_ids = list(dict.fromkeys(costumer_client_ids))
    if not deduped_client_ids:
        return {}

    instances = (
        db.session.query(Costumer)
        .filter(
            Costumer.team_id == team_id,
            Costumer.client_id.in_(deduped_client_ids),
        )
        .order_by(Costumer.id.asc())
        .all()
    )
    by_client_id: dict[str, Costumer] = {}
    for instance in instances:
        if not instance.client_id or instance.client_id in by_client_id:
            continue
        by_client_id[instance.client_id] = instance

    return by_client_id


def _load_costumers_by_email(
    team_id: int,
    normalized_email_keys: set[str],
) -> dict[str, Costumer]:
    if not normalized_email_keys:
        return {}

    rows = (
        db.session.query(Costumer)
        .filter(
            Costumer.team_id == team_id,
            Costumer.email.isnot(None),
            func.lower(Costumer.email).in_(list(normalized_email_keys)),
        )
        .order_by(Costumer.id.asc())
        .all()
    )
    by_email: dict[str, Costumer] = {}
    for row in rows:
        email_key = normalize_email(row.email)
        if not email_key or email_key in by_email:
            continue
        by_email[email_key] = row

    return by_email


def _load_costumers_by_phone(
    team_id: int,
    normalized_phone_keys: set[str],
) -> dict[str, Costumer]:
    if not normalized_phone_keys:
        return {}

    rows = (
        db.session.query(CostumerPhone, Costumer)
        .join(Costumer, Costumer.id == CostumerPhone.costumer_id)
        .filter(
            Costumer.team_id == team_id,
            CostumerPhone.team_id == team_id,
        )
        .order_by(CostumerPhone.id.asc())
        .all()
    )

    by_phone: dict[str, Costumer] = {}
    for phone_row, costumer in rows:
        normalized_key = normalized_phone_string(phone_row.phone)
        if not normalized_key or normalized_key in by_phone:
            continue
        if normalized_key not in normalized_phone_keys:
            continue
        by_phone[normalized_key] = costumer

    return by_phone
