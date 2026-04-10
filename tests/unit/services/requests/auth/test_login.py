import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.requests.auth.login import parse_login_request


def test_parse_login_request_rejects_non_object_payload():
    with pytest.raises(ValidationFailed):
        parse_login_request(None)


def test_parse_login_request_requires_fields():
    with pytest.raises(ValidationFailed):
        parse_login_request({"email": "user@example.com", "password": "secret"})


def test_parse_login_request_rejects_invalid_timezone():
    with pytest.raises(ValidationFailed):
        parse_login_request(
            {
                "email": "user@example.com",
                "password": "secret",
                "time_zone": "Invalid/Zone",
            }
        )


def test_parse_login_request_accepts_valid_iana_timezone():
    request = parse_login_request(
        {
            "email": "user@example.com",
            "password": "secret",
            "app_scope": "admin",
            "time_zone": "Europe/Stockholm",
        }
    )
    assert request.email == "user@example.com"
    assert request.password == "secret"
    assert request.app_scope == "admin"
    assert request.time_zone == "Europe/Stockholm"
