from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.requests.common.fields import (
    validate_forbidden,
    validate_unexpected,
)
from Delivery_app_BK.services.requests.common.types import (
    parse_client_id,
    parse_optional_int,
    parse_optional_string,
    parse_required_bool,
    parse_required_int,
    validate_int_list,
)

from .common import (
    normalize_email,
    normalize_operating_hours_entry,
    validate_and_normalize_phone,
    validate_unique_weekdays,
)


FORBIDDEN_FIELDS = {"team_id"}
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
NESTED_KEYS = {
    "addresses",
    "phones",
    "operating_hours",
    "delete_address_ids",
    "delete_phone_ids",
    "replace_operating_hours",
}
ALLOWED_UPDATE_FIELDS = SCALAR_MUTABLE_FIELDS | NESTED_KEYS


@dataclass
class CostumerUpdateTargetRequest:
    target_id: int
    fields: dict[str, Any]


def parse_update_costumer_target_request(raw_target: dict[str, Any]) -> CostumerUpdateTargetRequest:
    if not isinstance(raw_target, dict):
        raise ValidationFailed("Each target must be an object")
    target_id = raw_target.get("target_id")
    if not isinstance(target_id, int):
        raise ValidationFailed("Costumer update target_id must be an integer")

    fields = raw_target.get("fields")
    if not isinstance(fields, dict):
        raise ValidationFailed("'fields' must be a dictionary.")

    validate_forbidden(
        fields,
        FORBIDDEN_FIELDS,
        context_msg=f"Target '{target_id}' contains forbidden fields for this endpoint:",
    )
    validate_unexpected(
        fields,
        ALLOWED_UPDATE_FIELDS,
        context_msg=f"Target '{target_id}' contains unsupported fields for this endpoint:",
    )

    parsed: dict[str, Any] = {}
    parsed.update(_parse_scalar_fields(fields))
    parsed.update(_parse_nested_fields(fields))

    return CostumerUpdateTargetRequest(
        target_id=target_id,
        fields=parsed,
    )


def _parse_scalar_fields(fields: dict[str, Any]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    if "first_name" in fields:
        parsed["first_name"] = parse_optional_string(fields.get("first_name"), field="first_name")
    if "last_name" in fields:
        parsed["last_name"] = parse_optional_string(fields.get("last_name"), field="last_name")
    if "email" in fields:
        parsed["email"] = normalize_email(parse_optional_string(fields.get("email"), field="email"))
    if "external_source" in fields:
        parsed["external_source"] = parse_optional_string(
            fields.get("external_source"),
            field="external_source",
        )
    if "external_costumer_id" in fields:
        parsed["external_costumer_id"] = parse_optional_string(
            fields.get("external_costumer_id"),
            field="external_costumer_id",
        )
    if "default_address_id" in fields:
        parsed["default_address_id"] = parse_optional_int(
            fields.get("default_address_id"),
            field="default_address_id",
        )
    if "default_primary_phone_id" in fields:
        parsed["default_primary_phone_id"] = parse_optional_int(
            fields.get("default_primary_phone_id"),
            field="default_primary_phone_id",
        )
    if "default_secondary_phone_id" in fields:
        parsed["default_secondary_phone_id"] = parse_optional_int(
            fields.get("default_secondary_phone_id"),
            field="default_secondary_phone_id",
        )
    return parsed


def _parse_nested_fields(fields: dict[str, Any]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    if "delete_address_ids" in fields:
        parsed["delete_address_ids"] = validate_int_list(
            fields.get("delete_address_ids"),
            field="delete_address_ids",
        )
    if "delete_phone_ids" in fields:
        parsed["delete_phone_ids"] = validate_int_list(
            fields.get("delete_phone_ids"),
            field="delete_phone_ids",
        )
    if "replace_operating_hours" in fields:
        parsed["replace_operating_hours"] = parse_required_bool(
            fields.get("replace_operating_hours"),
            field="replace_operating_hours",
        )

    if "addresses" in fields:
        parsed["addresses"] = _parse_addresses(fields.get("addresses"))
    if "phones" in fields:
        parsed["phones"] = _parse_phones(fields.get("phones"))
    if "operating_hours" in fields:
        parsed["operating_hours"] = _parse_operating_hours(fields.get("operating_hours"))

    return parsed


def _parse_addresses(value: Any) -> list[dict[str, Any]]:
    payload = _parse_list_of_dicts(value, field="addresses")
    parsed: list[dict[str, Any]] = []
    default_count = 0

    for idx, entry in enumerate(payload):
        out: dict[str, Any] = {}
        if "id" in entry:
            out["id"] = parse_required_int(entry.get("id"), field=f"addresses[{idx}].id")

        if "client_id" in entry:
            out["client_id"] = parse_optional_string(
                entry.get("client_id"),
                field=f"addresses[{idx}].client_id",
            )
        elif "id" not in out:
            out["client_id"] = parse_client_id(
                None,
                prefix="costumer_address",
                field=f"addresses[{idx}].client_id",
            )

        if "label" in entry:
            out["label"] = parse_optional_string(entry.get("label"), field=f"addresses[{idx}].label")
        if "address" in entry:
            out["address"] = _parse_optional_dict(
                entry.get("address"),
                field=f"addresses[{idx}].address",
            )

        if "is_default" in entry:
            out["is_default"] = parse_required_bool(
                entry.get("is_default"),
                field=f"addresses[{idx}].is_default",
            )
            if out["is_default"]:
                default_count += 1

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
        out: dict[str, Any] = {}
        if "id" in entry:
            out["id"] = parse_required_int(entry.get("id"), field=f"phones[{idx}].id")

        if "client_id" in entry:
            out["client_id"] = parse_optional_string(
                entry.get("client_id"),
                field=f"phones[{idx}].client_id",
            )
        elif "id" not in out:
            out["client_id"] = parse_client_id(
                None,
                prefix="costumer_phone",
                field=f"phones[{idx}].client_id",
            )

        if "label" in entry:
            out["label"] = parse_optional_string(entry.get("label"), field=f"phones[{idx}].label")
        if "phone" in entry:
            out["phone"] = validate_and_normalize_phone(entry.get("phone"))
        if "phone_type" in entry:
            out["phone_type"] = parse_optional_string(
                entry.get("phone_type"),
                field=f"phones[{idx}].phone_type",
            )

        if "is_default_primary" in entry:
            out["is_default_primary"] = parse_required_bool(
                entry.get("is_default_primary"),
                field=f"phones[{idx}].is_default_primary",
            )
        if "is_default_secondary" in entry:
            out["is_default_secondary"] = parse_required_bool(
                entry.get("is_default_secondary"),
                field=f"phones[{idx}].is_default_secondary",
            )
        if out.get("is_default_primary") and out.get("is_default_secondary"):
            raise ValidationFailed(
                "A phone cannot be both is_default_primary and is_default_secondary"
            )

        if out.get("is_default_primary"):
            primary_count += 1
        if out.get("is_default_secondary"):
            secondary_count += 1

        parsed.append(out)

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
        row["client_id"] = parse_optional_string(
            entry.get("client_id"),
            field=f"operating_hours[{idx}].client_id",
        ) or parse_client_id(
            None,
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
        raise ValidationFailed(f"{field} is required when provided")
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

