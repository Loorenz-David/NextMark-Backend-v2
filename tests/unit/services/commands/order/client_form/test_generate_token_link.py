from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from Delivery_app_BK.services.commands.order.client_form import generate_token as module


def test_get_existing_client_form_url_returns_url_when_token_is_valid(monkeypatch):
    order = SimpleNamespace(
        client_form_token_hash="abc",
        client_form_token_encrypted="enc",
        client_form_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        client_form_submitted_at=None,
    )

    monkeypatch.setattr(module, "decrypt_secret", lambda _: "token123")
    monkeypatch.setattr(module.hashlib, "sha256", lambda *_args, **_kwargs: SimpleNamespace(hexdigest=lambda: "abc"))

    assert (
        module.get_existing_client_form_url(order, base_url="https://forms.nextmark.app")
        == "https://forms.nextmark.app/form/token123"
    )


def test_get_existing_client_form_url_returns_none_when_token_is_not_reusable():
    order = SimpleNamespace(
        client_form_token_hash=None,
        client_form_token_encrypted=None,
        client_form_token_expires_at=None,
        client_form_submitted_at=None,
    )

    assert module.get_existing_client_form_url(order) is None
