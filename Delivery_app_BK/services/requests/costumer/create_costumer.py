from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.requests.common.fields import (
    validate_forbidden,
    validate_required,
    validate_unexpected,
)
from Delivery_app_BK.services.requests.common.types import (
    parse_client_id,
    parse_optional_int,
    parse_optional_string,
    parse_required_bool,
    parse_required_int,
    validate_str,
)

from .common import (
    normalize_email,
    normalize_operating_hours_entry,
    validate_and_normalize_phone,
    validate_unique_weekdays,
)


ALLOWED_CREATE_FIELDS = {
    "client_id",
    "first_name",
    "last_name",
    "email",
    "external_source",
    "external_costumer_id",
    "default_address_id",
    "default_primary_phone_id",
    "default_secondary_phone_id",
    "addresses",
    "phones",
    "operating_hours",
}

FORBIDDEN_CREATE_FIELDS = {
    "id",
    "team_id",
    "orders",
    "addresses_ids",
    "phones_ids",
}

REQUIRED_CREATE_FIELDS = {
    "first_name",
    "last_name",
}


@dataclass
class CostumerCreateRequest:
    fields: dict[str, Any]
    addresses: list[dict[str, Any]]
    phones: list[dict[str, Any]]
    operating_hours: list[dict[str, Any]]


def parse_create_costumer_request(raw_fields: dict) -> CostumerCreateRequest:
    if not isinstance(raw_fields, dict):
        raise ValidationFailed("Each create payload in 'fields' must be an object.")

    validate_forbidden(
        raw_fields,
        FORBIDDEN_CREATE_FIELDS,
        context_msg="Forbidden fields in costumer create payload:",
    )
    validate_unexpected(
        raw_fields,
        ALLOWED_CREATE_FIELDS,
        context_msg="Unexpected fields in costumer create payload:",
    )
    validate_required(
        raw_fields,
        REQUIRED_CREATE_FIELDS,
        context_msg="Missing required fields for create costumer.",
    )

    fields = {
        "client_id": parse_client_id(raw_fields.get("client_id"), prefix="costumer"),
        "first_name": validate_str(raw_fields.get("first_name"), field="first_name"),
        "last_name": validate_str(raw_fields.get("last_name"), field="last_name"),
        "email": normalize_email(parse_optional_string(raw_fields.get("email"), field="email")),
        "external_source": parse_optional_string(
            raw_fields.get("external_source"),
            field="external_source",
        ),
        "external_costumer_id": parse_optional_string(
            raw_fields.get("external_costumer_id"),
            field="external_costumer_id",
        ),
    }

    if "default_address_id" in raw_fields:
        fields["default_address_id"] = parse_optional_int(
            raw_fields.get("default_address_id"),
            field="default_address_id",
        )
    if "default_primary_phone_id" in raw_fields:
        fields["default_primary_phone_id"] = parse_optional_int(
            raw_fields.get("default_primary_phone_id"),
            field="default_primary_phone_id",
        )
    if "default_secondary_phone_id" in raw_fields:
        fields["default_secondary_phone_id"] = parse_optional_int(
            raw_fields.get("default_secondary_phone_id"),
            field="default_secondary_phone_id",
        )

    addresses = _parse_addresses(raw_fields.get("addresses"))
    phones = _parse_phones(raw_fields.get("phones"))
    operating_hours = _parse_operating_hours(raw_fields.get("operating_hours"))

    return CostumerCreateRequest(
        fields=fields,
        addresses=addresses,
        phones=phones,
        operating_hours=operating_hours,
    )


def _parse_addresses(value: Any) -> list[dict[str, Any]]:
    payload = _parse_list_of_dicts(value, field="addresses")
    parsed: list[dict[str, Any]] = []
    default_count = 0

    for idx, entry in enumerate(payload):
        out = {
            "client_id": parse_client_id(
                entry.get("client_id"),
                prefix="costumer_address",
                field=f"addresses[{idx}].client_id",
            ),
            "label": parse_optional_string(entry.get("label"), field=f"addresses[{idx}].label"),
            "address": _parse_optional_dict(entry.get("address"), field=f"addresses[{idx}].address"),
        }
        if "is_default" in entry:
            out["is_default"] = parse_required_bool(
                entry.get("is_default"),
                field=f"addresses[{idx}].is_default",
            )
            if out["is_default"]:
                default_count += 1
        else:
            out["is_default"] = False
        parsed.append(out)

    if default_count > 1:
        raise ValidationFailed("Only one addresses[].is_default is allowed")
    return parsed


def _parse_phones(value: Any) -> list[dict[str, Any]]:
    payload = _parse_list_of_dicts(value, field="phones")
    parsed: list[dict[str, Any]] = []
    primary_count = 0
    secondary_count = 0

    for idx, entry in enumerate(payload):
        is_primary = parse_required_bool(
            entry.get("is_default_primary"),
            field=f"phones[{idx}].is_default_primary",
        ) if "is_default_primary" in entry else False
        is_secondary = parse_required_bool(
            entry.get("is_default_secondary"),
            field=f"phones[{idx}].is_default_secondary",
        ) if "is_default_secondary" in entry else False
        if is_primary and is_secondary:
            raise ValidationFailed(
                "A phone cannot be both is_default_primary and is_default_secondary"
            )
        if is_primary:
            primary_count += 1
        if is_secondary:
            secondary_count += 1

        parsed.append(
            {
                "client_id": parse_client_id(
                    entry.get("client_id"),
                    prefix="costumer_phone",
                    field=f"phones[{idx}].client_id",
                ),
                "label": parse_optional_string(entry.get("label"), field=f"phones[{idx}].label"),
                "phone": validate_and_normalize_phone(entry.get("phone")),
                "phone_type": parse_optional_string(
                    entry.get("phone_type"),
                    field=f"phones[{idx}].phone_type",
                ),
                "is_default_primary": is_primary,
                "is_default_secondary": is_secondary,
            }
        )

    if primary_count > 1:
        raise ValidationFailed("Only one phones[].is_default_primary is allowed")
    if secondary_count > 1:
        raise ValidationFailed("Only one phones[].is_default_secondary is allowed")
    return parsed


def _parse_operating_hours(value: Any) -> list[dict[str, Any]]:
    payload = _parse_list_of_dicts(value, field="operating_hours")
    parsed: list[dict[str, Any]] = []
    for idx, entry in enumerate(payload):
        row = dict(entry)
        row["client_id"] = parse_client_id(
            entry.get("client_id"),
            prefix="costumer_operating_hours",
            field=f"operating_hours[{idx}].client_id",
        )
        row["weekday"] = parse_required_int(entry.get("weekday"), field=f"operating_hours[{idx}].weekday")
        if "is_closed" in entry:
            row["is_closed"] = parse_required_bool(
                entry.get("is_closed"),
                field=f"operating_hours[{idx}].is_closed",
            )
        parsed.append(normalize_operating_hours_entry(row))

    validate_unique_weekdays(parsed)
    return parsed


def _parse_list_of_dicts(value: Any, *, field: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationFailed(f"{field} must be a list")
    for index, entry in enumerate(value):
        if not isinstance(entry, dict):
            raise ValidationFailed(f"{field}[{index}] must be an object")
    return value


def _parse_optional_dict(value: Any, *, field: str) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValidationFailed(f"{field} must be an object")
    return value

