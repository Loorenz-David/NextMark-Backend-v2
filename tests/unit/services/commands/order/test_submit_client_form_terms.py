"""Terms acceptance recorded by a client-form submission."""

from types import SimpleNamespace

import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.commands.order.client_form import submit_client_form as module


def _order():
    return SimpleNamespace(
        id=42,
        team_id=7,
        client_email="old@example.com",
        client_form_token_encrypted="encrypted-token",
        client_form_submitted_at=None,
        accepted_terms_version_id=None,
        terms_accepted_at=None,
    )


@pytest.fixture(autouse=True)
def _isolate_side_effects(monkeypatch):
    monkeypatch.setattr(module, "emit_order_events", lambda ctx, events: None)
    monkeypatch.setattr(module.db.session, "commit", lambda: None)


def test_submit_stamps_accepted_terms_version(monkeypatch):
    order = _order()
    accepted = SimpleNamespace(id=12, version_number=4)

    monkeypatch.setattr(module, "validate_and_get_order", lambda token: order)
    monkeypatch.setattr(module, "resolve_terms_acceptance", lambda team_id, payload: accepted)

    result = module.submit_client_form(
        "valid-token", {"client_email": "new@example.com", "accepted_terms_version_id": 12}
    )

    assert result == {"success": True}
    assert order.accepted_terms_version_id == 12
    assert order.terms_accepted_at is not None
    assert order.terms_accepted_at == order.client_form_submitted_at


def test_submit_leaves_terms_columns_unset_when_team_collects_no_acceptance(monkeypatch):
    order = _order()

    monkeypatch.setattr(module, "validate_and_get_order", lambda token: order)
    monkeypatch.setattr(module, "resolve_terms_acceptance", lambda team_id, payload: None)

    module.submit_client_form("valid-token", {"client_email": "new@example.com"})

    assert order.accepted_terms_version_id is None
    assert order.terms_accepted_at is None
    assert order.client_form_submitted_at is not None


def test_submit_rejects_before_writing_when_acceptance_invalid(monkeypatch):
    """A rejected acceptance must leave the order untouched — token included."""
    order = _order()

    def _reject(team_id, payload):
        raise ValidationFailed("You must accept the terms and conditions to submit this form.")

    monkeypatch.setattr(module, "validate_and_get_order", lambda token: order)
    monkeypatch.setattr(module, "resolve_terms_acceptance", _reject)

    with pytest.raises(ValidationFailed):
        module.submit_client_form("valid-token", {"client_email": "new@example.com"})

    assert order.client_email == "old@example.com"
    assert order.client_form_submitted_at is None
    assert order.client_form_token_encrypted == "encrypted-token"


def test_accepted_terms_version_id_is_not_a_blind_copy_field():
    """It must stay outside ALLOWED_CLIENT_FIELDS — that set is written unchecked."""
    assert "accepted_terms_version_id" not in module.ALLOWED_CLIENT_FIELDS
