from dataclasses import dataclass, field

from Delivery_app_BK.errors import ValidationFailed

from ..common.types import validate_str, parse_required_bool


def _validate_client_id_list(value, *, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationFailed(f"{field_name} must be a list.")
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        parsed = validate_str(item, field=field_name)
        if parsed not in seen:
            seen.add(parsed)
            result.append(parsed)
    return result


@dataclass(frozen=True)
class RegisterTrustedDeviceRequest:
    name: str
    user_client_ids: list[str]


def parse_register_trusted_device(raw: dict) -> RegisterTrustedDeviceRequest:
    if not isinstance(raw, dict):
        raise ValidationFailed("Payload must be an object.")
    name = validate_str(raw.get("name"), field="name")
    user_client_ids = _validate_client_id_list(
        raw.get("user_client_ids"), field_name="user_client_ids"
    )
    return RegisterTrustedDeviceRequest(name=name, user_client_ids=user_client_ids)


@dataclass
class UpdateTrustedDeviceRequest:
    name: str | None = None
    is_active: bool | None = None
    provided_fields: set[str] = field(default_factory=set, repr=False)


def parse_update_trusted_device(raw: dict) -> UpdateTrustedDeviceRequest:
    if not isinstance(raw, dict):
        raise ValidationFailed("Payload must be an object.")

    provided: set[str] = set()
    name = None
    is_active = None

    if "name" in raw:
        name = validate_str(raw.get("name"), field="name")
        provided.add("name")
    if "is_active" in raw:
        is_active = parse_required_bool(raw.get("is_active"), field="is_active")
        provided.add("is_active")

    if not provided:
        raise ValidationFailed("No updatable fields were provided.")

    return UpdateTrustedDeviceRequest(
        name=name, is_active=is_active, provided_fields=provided
    )


@dataclass(frozen=True)
class AssignTrustedDeviceUserRequest:
    user_client_id: str


def parse_assign_trusted_device_user(raw: dict) -> AssignTrustedDeviceUserRequest:
    if not isinstance(raw, dict):
        raise ValidationFailed("Payload must be an object.")
    user_client_id = validate_str(raw.get("user_client_id"), field="user_client_id")
    return AssignTrustedDeviceUserRequest(user_client_id=user_client_id)
