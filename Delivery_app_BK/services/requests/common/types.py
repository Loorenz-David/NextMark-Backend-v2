from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from Delivery_app_BK.services.commands.utils import generate_client_id
from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.zones.services.city_key_normalizer import normalize_city_key


def validate_str(
    value,
    *,
    field: str,
    allow_none: bool = False,
) -> str | None:
    if value is None:
        if allow_none:
            return None
        raise ValidationFailed(f"{field} is required.")

    if not isinstance(value, str):
        raise ValidationFailed(f"{field} must be a string.")

    normalized = value.strip()
    if not normalized:
        raise ValidationFailed(f"{field} cannot be empty.")
    return normalized


def validate_int_list(value, *, field: str) -> list[int]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationFailed(f"{field} must be a list of integers.")

    for item in value:
        if not isinstance(item, int) or isinstance(item, bool):
            raise ValidationFailed(f"{field} must be a list of integers.")

    return list(dict.fromkeys(value))


def parse_client_id(
    value,
    *,
    prefix: str,
    field: str = "client_id",
) -> str:
    parsed = parse_optional_string(value, field=field)
    if parsed:
        return parsed
    return generate_client_id(prefix)


def parse_optional_string(value, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationFailed(f"{field} must be a string.")
    normalized = value.strip()
    return normalized or None


def parse_required_int(value, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationFailed(f"{field} must be an integer.")
    return value


def parse_optional_int(value, *, field: str) -> int | None:
    if value is None:
        return None
    return parse_required_int(value, field=field)


def parse_required_bool(value, *, field: str) -> bool:
    if type(value) is not bool:
        raise ValidationFailed(f"{field} must be a boolean.")
    return value


def parse_optional_dict(value, *, field: str) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValidationFailed(f"{field} must be an object.")
    return value


def parse_optional_json(value, *, field: str):
    if value is None:
        return None
    if not isinstance(value, (dict, list)):
        raise ValidationFailed(f"{field} must be a JSON object or array.")
    return value


def parse_optional_time_zone(value, *, field: str = "time_zone") -> str | None:
    parsed = parse_optional_string(value, field=field)
    if parsed is None:
        return None

    try:
        ZoneInfo(parsed)
    except ZoneInfoNotFoundError as exc:
        raise ValidationFailed(f"{field} must be a valid IANA timezone.") from exc

    return parsed


def parse_optional_country_code(value, *, field: str = "country_code") -> str | None:
    parsed = parse_optional_string(value, field=field)
    if parsed is None:
        return None

    normalized = parsed.upper()
    if len(normalized) != 2 or not normalized.isalpha():
        raise ValidationFailed(f"{field} must be a valid ISO 3166-1 alpha-2 country code.")

    return normalized


def parse_optional_city_key(value, *, field: str = "city_key") -> str | None:
    parsed = parse_optional_string(value, field=field)
    if parsed is None:
        return None

    normalized = normalize_city_key(parsed)
    if normalized == "unknown_city":
        raise ValidationFailed(f"{field} must contain letters or numbers.")

    return normalized


def parse_required_time_zone(value, *, field: str = "time_zone") -> str:
    parsed = parse_optional_time_zone(value, field=field)
    if parsed is None:
        raise ValidationFailed(f"{field} is required.")
    return parsed
