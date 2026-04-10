from dataclasses import dataclass

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.domain.user import parse_app_scope
from Delivery_app_BK.services.requests.common.types import (
    parse_optional_time_zone,
    validate_str,
)


@dataclass(frozen=True)
class LoginRequest:
    email: str
    password: str
    app_scope: str
    time_zone: str | None



def parse_login_request(raw: dict) -> LoginRequest:
    if not isinstance(raw, dict):
        raise ValidationFailed("Payload must be an object.")

    email = validate_str(raw.get("email"), field="email")
    password = validate_str(raw.get("password"), field="password")
    app_scope = parse_app_scope(raw.get("app_scope"))
    time_zone = parse_optional_time_zone(raw.get("time_zone"), field="time_zone")
    
    return LoginRequest(
        email=email,
        password=password,
        app_scope=app_scope,
        time_zone=time_zone,
    )
