from types import SimpleNamespace

import pytest

from Delivery_app_BK.services.commands.order.client_form import send_link as module


def test_send_client_form_link_messages_queues_email_and_sms():
    order = SimpleNamespace(
        client_email="client@example.com",
        client_primary_phone={"prefix": "+1", "number": "5550100"},
    )

    results = module.send_client_form_link_messages(
        order=order,
        form_url="https://forms.nextmark.app/form/token123",
        recipients={
            "email": "client@example.com",
            "sms": {"prefix": "+1", "number": "5550100"},
        },
    )

    assert results == {
        "email": {"status": "queued", "recipient": "client@example.com"},
        "sms": {"status": "queued", "recipient": "+15550100"},
    }


def test_send_client_form_link_messages_uses_recipient_overrides():
    order = SimpleNamespace(
        client_email="client@example.com",
        client_primary_phone={"prefix": "+1", "number": "5550100"},
    )

    results = module.send_client_form_link_messages(
        order=order,
        form_url="https://forms.nextmark.app/form/token123",
        recipients={
            "email": "other@example.com",
            "sms": {"prefix": "+46", "number": "2020203"},
        },
    )

    assert results == {
        "email": {"status": "queued", "recipient": "other@example.com"},
        "sms": {"status": "queued", "recipient": "+462020203"},
    }


def test_send_client_form_link_messages_reports_missing_recipient():
    order = SimpleNamespace(client_email=None, client_primary_phone=None)

    with pytest.raises(module.ValidationFailed, match="requires at least one recipient"):
        module.send_client_form_link_messages(
            order=order,
            form_url="https://forms.nextmark.app/form/token123",
            recipients={},
        )


def test_send_client_form_link_messages_reports_missing_email_on_order():
    order = SimpleNamespace(client_email="", client_primary_phone=None)

    results = module.send_client_form_link_messages(
        order=order,
        form_url="https://forms.nextmark.app/form/token123",
        recipients={"email": ""},
    )

    assert results == {
        "email": {
            "status": "failed",
            "detail": "Missing client email on order.",
        }
    }


def test_parse_recipients_accepts_email_and_sms_object():
    recipients = module.parse_recipients(
        {
            "recipients": {
                "email": "other@example.com",
                "sms": {"prefix": "+46", "number": "2020203"},
            }
        }
    )

    assert recipients == {
        "email": "other@example.com",
        "sms": {"prefix": "+46", "number": "2020203"},
    }


def test_parse_recipients_rejects_invalid_sms_shape():
    with pytest.raises(module.ValidationFailed, match="SMS recipient must be a string or object"):
        module.parse_recipients({"recipients": {"sms": ["bad"]}})


def test_parse_recipients_rejects_unknown_keys():
    with pytest.raises(module.ValidationFailed, match="Unsupported client form recipient keys"):
        module.parse_recipients({"recipients": {"whatsapp": "+1555"}})


def test_send_client_form_link_generates_and_sends(monkeypatch):
    expires_at = SimpleNamespace(isoformat=lambda: "2026-04-04T00:00:00+00:00")
    order = SimpleNamespace(id=10, client_email="client@example.com")
    emitted_payloads: list[dict] = []

    monkeypatch.setattr(
        module,
        "get_or_generate_client_form_token",
        lambda order_id, team_id: {
            "raw_token": "token123",
            "expires_at": expires_at,
            "order": order,
            "reused": True,
        },
    )
    monkeypatch.setattr(
        module,
        "send_client_form_link_messages",
        lambda **kwargs: {"email": {"status": "queued", "recipient": "client@example.com"}},
    )
    monkeypatch.setattr(
        module,
        "emit_order_events",
        lambda ctx, events: emitted_payloads.extend(events),
    )

    result = module.send_client_form_link(
        order_id=10,
        team_id=5,
        base_url="https://forms.nextmark.app",
        identity={"team_id": 5, "user_id": 77},
        payload={"recipients": {"email": "client@example.com"}},
    )

    assert result == {
        "form_url": "https://forms.nextmark.app/form/token123",
        "expires_at": expires_at,
        "reused": True,
        "send_results": {"email": {"status": "queued", "recipient": "client@example.com"}},
    }
    assert emitted_payloads == [
        {
            "order_id": 10,
            "event_name": module.CLIENT_FORM_LINK_EVENT,
            "team_id": 5,
            "payload": {
                "recipients": {"email": "client@example.com"},
            },
        }
    ]


def test_send_client_form_link_persists_recipient_overrides_to_order(monkeypatch):
    expires_at = SimpleNamespace(isoformat=lambda: "2026-04-04T00:00:00+00:00")
    order = SimpleNamespace(
        id=10,
        client_email="old@example.com",
        client_primary_phone={"prefix": "+1", "number": "1111111"},
    )

    monkeypatch.setattr(
        module,
        "get_or_generate_client_form_token",
        lambda order_id, team_id: {
            "raw_token": "token123",
            "expires_at": expires_at,
            "order": order,
            "reused": True,
        },
    )
    monkeypatch.setattr(
        module,
        "emit_order_events",
        lambda ctx, events: None,
    )

    module.send_client_form_link(
        order_id=10,
        team_id=5,
        base_url="https://forms.nextmark.app",
        identity={"team_id": 5, "user_id": 77},
        payload={
            "recipients": {
                "email": "new@example.com",
                "sms": {"prefix": "+46", "number": "2020203"},
            }
        },
    )

    assert order.client_email == "new@example.com"
    assert order.client_primary_phone == {"prefix": "+46", "number": "2020203"}