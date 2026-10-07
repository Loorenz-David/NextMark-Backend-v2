from types import SimpleNamespace

import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.commands.integration_email import update_email_config as module
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.utils.crypto import decrypt_secret, encrypt_secret


@pytest.fixture(autouse=True)
def _crypto_key(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "unit-test-secret")


@pytest.fixture
def integration(monkeypatch):
    stored = SimpleNamespace(
        id=4,
        smtp_server="smtp.example.com",
        smtp_port=587,
        smtp_username="ops@example.com",
        smtp_password=encrypt_secret("old-app-password"),
        use_tls=True,
        use_ssl=False,
        max_per_session=50,
    )
    monkeypatch.setattr(module, "get_instance", lambda ctx, model, lookup_id: stored)
    monkeypatch.setattr(module, "serialize_email_integration", lambda instance: {"id": instance.id})
    monkeypatch.setattr(module.db.session, "commit", lambda: None)
    return stored


def test_plain_password_from_client_is_encrypted_before_storage(integration):
    ctx = ServiceContext(incoming_data={"smtp_password": "new-app-password"})

    module.update_email_config(ctx, "4")

    assert integration.smtp_password != "new-app-password"
    assert decrypt_secret(integration.smtp_password) == "new-app-password"


def test_already_encrypted_password_is_rejected(integration):
    ctx = ServiceContext(incoming_data={"smtp_password": integration.smtp_password})

    with pytest.raises(ValidationFailed, match="Encrypted SMTP passwords are not accepted"):
        module.update_email_config(ctx, "4")

    assert decrypt_secret(integration.smtp_password) == "old-app-password"


@pytest.mark.parametrize("value", ["", "   ", None, 123])
def test_blank_or_non_string_password_is_rejected(integration, value):
    ctx = ServiceContext(incoming_data={"smtp_password": value})

    with pytest.raises(ValidationFailed, match="non-empty string"):
        module.update_email_config(ctx, "4")


def test_other_fields_update_without_touching_the_password(integration):
    ctx = ServiceContext(incoming_data={"smtp_port": 465, "use_ssl": True, "ignored": "x"})

    module.update_email_config(ctx, "4")

    assert integration.smtp_port == 465
    assert integration.use_ssl is True
    assert decrypt_secret(integration.smtp_password) == "old-app-password"
