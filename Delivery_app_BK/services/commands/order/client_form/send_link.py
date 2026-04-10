from __future__ import annotations

from typing import Any

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.commands.order.client_form.generate_token import get_or_generate_client_form_token
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.domain.order.order_events import OrderEvent
from Delivery_app_BK.services.infra.events.emiters.order import emit_order_events
from Delivery_app_BK.services.infra.messaging.label_resolvers import phone_to_string


CLIENT_FORM_LINK_EVENT = OrderEvent.CLIENT_FORM_LINK_SENT.value
SUPPORTED_CLIENT_FORM_CHANNELS = {"email", "sms"}


def _build_result(status: str, *, detail: str | None = None, recipient: str | None = None) -> dict[str, str]:
    result = {"status": status}
    if detail:
        result["detail"] = detail
    if recipient:
        result["recipient"] = recipient
    return result


def parse_recipients(payload: dict[str, Any]) -> dict[str, Any]:
    raw_recipients = payload.get("recipients")
    if raw_recipients is None:
        return {}

    if not isinstance(raw_recipients, dict):
        raise ValidationFailed("Client form recipients must be a JSON object.")

    invalid_keys = sorted(set(raw_recipients) - SUPPORTED_CLIENT_FORM_CHANNELS)
    if invalid_keys:
        raise ValidationFailed(
            f"Unsupported client form recipient keys: {', '.join(invalid_keys)}. "
            f"Allowed keys: {', '.join(sorted(SUPPORTED_CLIENT_FORM_CHANNELS))}."
        )

    recipients: dict[str, Any] = {}
    email_recipient = raw_recipients.get("email")
    if email_recipient is not None:
        if not isinstance(email_recipient, str):
            raise ValidationFailed("Client form email recipient must be a string.")
        recipients["email"] = email_recipient.strip()

    sms_recipient = raw_recipients.get("sms")
    if sms_recipient is not None:
        if isinstance(sms_recipient, str):
            recipients["sms"] = sms_recipient.strip()
        elif isinstance(sms_recipient, dict):
            recipients["sms"] = sms_recipient
        else:
            raise ValidationFailed("Client form SMS recipient must be a string or object.")

    return recipients


def _derive_channels_from_recipients(recipients: dict[str, Any]) -> list[str]:
    channels: list[str] = []
    if "email" in recipients:
        channels.append("email")
    if "sms" in recipients:
        channels.append("sms")

    if not channels:
        raise ValidationFailed("Client form send request requires at least one recipient: email or sms.")

    return channels


def _resolve_email_recipient(order: object, recipient_override: object | None) -> str:
    if isinstance(recipient_override, str):
        return recipient_override.strip()
    return (getattr(order, "client_email", None) or "").strip()


def _resolve_sms_recipient(order: object, recipient_override: object | None) -> str:
    if recipient_override is not None:
        return phone_to_string(recipient_override).strip()
    return phone_to_string(getattr(order, "client_primary_phone", None)).strip()


def _queue_email(order: object, recipient_override: object | None) -> dict[str, str]:
    recipient = _resolve_email_recipient(order, recipient_override)
    if not recipient:
        return _build_result("failed", detail="Missing client email on order.")
    return _build_result("queued", recipient=recipient)


def _queue_sms(order: object, recipient_override: object | None) -> dict[str, str]:
    recipient = _resolve_sms_recipient(order, recipient_override)
    if not recipient:
        return _build_result("failed", detail="Missing client primary phone on order.")
    return _build_result("queued", recipient=recipient)


def send_client_form_link_messages(
    *,
    order: object,
    form_url: str,
    recipients: dict[str, Any] | None = None,
) -> dict[str, dict[str, str]]:
    results: dict[str, dict[str, str]] = {}
    recipients = recipients or {}
    channels = _derive_channels_from_recipients(recipients)

    for channel in channels:
        if channel == "email":
            results[channel] = _queue_email(
                order,
                recipients.get("email"),
            )
        elif channel == "sms":
            results[channel] = _queue_sms(
                order,
                recipients.get("sms"),
            )

    return results


def _build_event_payload(*, recipients: dict[str, Any]) -> dict[str, Any]:
    return {
        "recipients": recipients,
    }


def _persist_recipient_overrides_to_order(order: object, recipients: dict[str, Any]) -> None:
    email_value = recipients.get("email")
    if isinstance(email_value, str) and email_value.strip():
        setattr(order, "client_email", email_value.strip())

    # Order.client_primary_phone uses JSON schema {"prefix": str, "number": str}.
    sms_value = recipients.get("sms")
    if isinstance(sms_value, dict):
        setattr(order, "client_primary_phone", sms_value)


def _emit_client_form_link_event(*, order_id: int, team_id: int, identity: dict[str, Any], payload: dict[str, Any]) -> None:
    ctx = ServiceContext(identity=identity)
    emit_order_events(
        ctx,
        [
            {
                "order_id": order_id,
                "event_name": CLIENT_FORM_LINK_EVENT,
                "team_id": team_id,
                "payload": payload,
            }
        ],
    )


def send_client_form_link(
    *,
    order_id: int,
    team_id: int,
    base_url: str,
    identity: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValidationFailed("Request body must be a JSON object.")

    recipients = parse_recipients(payload)

    result = get_or_generate_client_form_token(order_id, team_id)
    form_url = f"{base_url}/form/{result['raw_token']}"
    _persist_recipient_overrides_to_order(result["order"], recipients)
    send_results = send_client_form_link_messages(
        order=result["order"],
        form_url=form_url,
        recipients=recipients,
    )

    event_payload = _build_event_payload(
        recipients=recipients,
    )
    _emit_client_form_link_event(
        order_id=order_id,
        team_id=team_id,
        identity=identity,
        payload=event_payload,
    )

    return {
        "form_url": form_url,
        "expires_at": result["expires_at"],
        "reused": result["reused"],
        "send_results": send_results,
    }