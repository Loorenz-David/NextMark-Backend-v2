from __future__ import annotations

from Delivery_app_BK.models import MessageTemplate, TwilioMod, db
from Delivery_app_BK.services.infra.messaging.body_builder import build_message_body
from Delivery_app_BK.services.infra.messaging.label_resolvers import MessageRenderContext
from Delivery_app_BK.services.infra.messaging.sms_provider import build_sms_provider


def _load_team_twilio(team_id: int | None) -> TwilioMod | None:
    if team_id is None:
        return None

    return (
        db.session.query(TwilioMod)
        .filter(TwilioMod.team_id == team_id)
        .order_by(TwilioMod.id.desc())
        .first()
    )


def send_sms_message(
    *,
    team_id: int,
    template: MessageTemplate,
    recipient_phone: str,
    event_name: str,
    render_context: MessageRenderContext,
) -> None:
    errors = send_sms_batch(
        team_id=team_id,
        template=template,
        recipients=[(0, recipient_phone, render_context)],
        event_name=event_name,
    )
    if errors:
        first_error = next(iter(errors.values()))
        raise RuntimeError(first_error)


def send_sms_batch(
    *,
    team_id: int,
    template: MessageTemplate,
    recipients: list[tuple[int, str, MessageRenderContext]],
    event_name: str,
) -> dict[int, str]:
    """
    The caller resolves and validates the template (event, channel and plan
    type) before calling; this layer only renders and sends it.
    """
    if not recipients:
        return {}

    twilio_integration = _load_team_twilio(team_id)
    if twilio_integration is None:
        raise RuntimeError("No Twilio configuration for team")

    sms_provider = build_sms_provider(twilio_integration)
    sms_provider.validate_connection()

    recipient_errors: dict[int, str] = {}
    for order_id, raw_recipient, render_context in recipients:
        to_number = raw_recipient.strip()
        if not to_number:
            recipient_errors[order_id] = "Missing SMS recipient phone"
            continue

        try:
            body = build_message_body(template.template, render_context, channel="sms")
            if not body.strip():
                recipient_errors[order_id] = "Resolved SMS body is empty"
                continue

            sms_provider.send_message(to_number=to_number, body=body)
        except Exception as exc:
            recipient_errors[order_id] = str(exc)

    return recipient_errors
