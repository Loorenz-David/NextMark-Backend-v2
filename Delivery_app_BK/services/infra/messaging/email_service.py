from __future__ import annotations

from email.message import EmailMessage
import html
import logging
from pathlib import Path
import re
import smtplib
import ssl
from typing import Any

from Delivery_app_BK.models import EmailSMTP, MessageTemplate, db
from Delivery_app_BK.services.infra.messaging.body_builder import build_message_body
from Delivery_app_BK.services.infra.messaging.label_resolvers import (
    MessageRenderContext,
    has_label_resolver,
    resolve_label,
)
from Delivery_app_BK.services.utils.crypto import decrypt_secret

HTML_TEMPLATE_FILE = "email_template_test.html"
HEADER_PLACEHOLDER = "{{HEADER_CONTENT}}"
BODY_PLACEHOLDER = "{{BODY_CONTENT}}"
FOOTER_PLACEHOLDER = "{{FOOTER_BUTTONS}}"
LABEL_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")
logger = logging.getLogger(__name__)


def _preview(text: str, max_len: int = 400) -> str:
    if len(text) <= max_len:
        return text
    return f"{text[:max_len]}..."


def _load_team_smtp(team_id: int | None) -> EmailSMTP | None:
    if team_id is None:
        return None

    return (
        db.session.query(EmailSMTP)
        .filter(EmailSMTP.team_id == team_id)
        .order_by(EmailSMTP.id.desc())
        .first()
    )


def _open_validated_smtp_client(smtp_config: EmailSMTP) -> smtplib.SMTP:
    if smtp_config.use_ssl:
        smtp_client = smtplib.SMTP_SSL(
            smtp_config.smtp_server,
            smtp_config.smtp_port,
            timeout=10,
            context=ssl.create_default_context(),
        )
        smtp_client.ehlo()
    else:
        smtp_client = smtplib.SMTP(
            smtp_config.smtp_server,
            smtp_config.smtp_port,
            timeout=10,
        )
        smtp_client.ehlo()
        if smtp_config.use_tls:
            smtp_client.starttls(context=ssl.create_default_context())
            smtp_client.ehlo()

    password = decrypt_secret(smtp_config.smtp_password)

    smtp_client.login(smtp_config.smtp_username, password)
    return smtp_client


def _replace_subject_labels(text: str, render_context: MessageRenderContext) -> str:
    def _replace(match: re.Match[str]) -> str:
        label_key = match.group(1)
        return resolve_label(label_key, render_context, channel="email")

    return LABEL_PATTERN.sub(_replace, text)


def _render_subject_value(subject_value: Any, render_context: MessageRenderContext) -> str:
    if subject_value is None:
        return ""

    if isinstance(subject_value, str):
        return _replace_subject_labels(subject_value, render_context)

    if isinstance(subject_value, list):
        return build_message_body(subject_value, render_context, channel="email_subject")

    if isinstance(subject_value, dict):
        return build_message_body([subject_value], render_context, channel="email_subject")

    return ""


def _normalize_email_subject(subject: str) -> str:
    return " ".join(subject.replace("\r", " ").replace("\n", " ").split())


def _build_subject(
    template: MessageTemplate,
    event_name: str,
    render_context: MessageRenderContext | None = None,
) -> str:
    if render_context is not None:
        rendered_subject = _normalize_email_subject(
            _render_subject_value(template.subject, render_context)
        )
        if rendered_subject:
            return rendered_subject

    template_name = (template.name or "").strip()
    if template_name:
        return template_name
    return event_name.replace("_", " ").title()


def resolve_template(team_id: int, channel: str, event_name: str) -> MessageTemplate | None:
    return (
        db.session.query(MessageTemplate)
        .filter(
            MessageTemplate.team_id == team_id,
            MessageTemplate.channel == channel,
            MessageTemplate.event == event_name,
        )
        .first()
    )


def _load_base_email_template() -> str:
    template_path = Path(__file__).resolve().parent.parent / "tasks" / "order" / HTML_TEMPLATE_FILE
    if not template_path.exists():
        raise FileNotFoundError(f"Base email template not found: {template_path}")
    return template_path.read_text(encoding="utf-8")


def _resolve_url_template(url_template: Any, render_context: MessageRenderContext) -> str:
    if isinstance(url_template, list):
        return build_message_body(url_template, render_context, channel="email").strip()

    if isinstance(url_template, dict):
        return build_message_body([url_template], render_context, channel="email").strip()

    if not isinstance(url_template, str):
        return ""

    raw_url = url_template.strip()
    if not raw_url:
        return ""

    def _replace(match: re.Match[str]) -> str:
        label_key = match.group(1)
        return resolve_label(label_key, render_context, channel="email")

    # Support links provided directly as label keys (e.g. "tracking_link").
    if has_label_resolver(raw_url):
        return resolve_label(raw_url, render_context, channel="email").strip()

    return LABEL_PATTERN.sub(_replace, raw_url).strip()


def _coerce_buttons(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


def _resolve_button_label(button: dict[str, Any], render_context: MessageRenderContext) -> str:
    label_value = button.get("label")
    if label_value is None:
        label_value = button.get("text")
    if label_value is None:
        label_value = button.get("title")

    if isinstance(label_value, str):
        return label_value.strip()

    if isinstance(label_value, (list, dict)):
        rendered = build_message_body(_coerce_buttons(label_value), render_context, channel="email")
        return rendered.strip()

    return ""


def _resolve_button_url(button: dict[str, Any], render_context: MessageRenderContext) -> str:
    for key in ("urlTemplate", "url_template", "url", "link", "href"):
        if key in button:
            return _resolve_url_template(button.get(key), render_context)
    return ""


def _render_footer_buttons(buttons: Any, render_context: MessageRenderContext) -> str:
    normalized_buttons = _coerce_buttons(buttons)
    if not normalized_buttons:
        return ""

    button_html_blocks: list[str] = []
    for button in normalized_buttons:
        if not isinstance(button, dict):
            continue

        label = _resolve_button_label(button, render_context)
        if not label:
            continue

        resolved_url = _resolve_button_url(button, render_context)
        if not resolved_url:
            continue

        safe_label = html.escape(label)
        safe_url = html.escape(resolved_url, quote=True)
        if not safe_label:
            continue

        button_html_blocks.append(
            (
                "<table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" role=\"presentation\">"
                "<tr>"
                "<td align=\"left\">"
                f"<a href=\"{safe_url}\" target=\"_blank\" style=\"display:inline-block;padding:8px 16px;"
                "font-family:Arial, Helvetica, sans-serif;font-size:14px;font-weight:bold;color:#ffffff;"
                "background-color:#007BFF;text-decoration:none;border-radius:999px;text-align:center;\">"
                f"{safe_label}</a>"
                "</td>"
                "</tr>"
                "</table>"
            )
        )

    return "".join(button_html_blocks)


def _extract_email_template_sections(template_value: Any) -> tuple[Any, Any, Any]:
    if isinstance(template_value, dict):
        header = template_value.get("header")
        body = template_value.get("body")
        buttons = template_value.get("footerButtons")
        if buttons is None:
            buttons = template_value.get("footer_buttons")
        if buttons is None:
            buttons = template_value.get("buttons")
        return header, body, buttons

    return [], template_value, []


def _render_email_html(template_value: Any, render_context: MessageRenderContext) -> str:
    header_value, body_value, buttons_value = _extract_email_template_sections(template_value)
    rendered_header = build_message_body(header_value, render_context, channel="email")
    rendered_body = build_message_body(body_value, render_context, channel="email")
    rendered_buttons = _render_footer_buttons(buttons_value, render_context)
    logger.debug(
        "Rendered email sections | header_len=%d body_len=%d buttons_len=%d header_preview=%r body_preview=%r",
        len(rendered_header),
        len(rendered_body),
        len(rendered_buttons),
        _preview(rendered_header),
        _preview(rendered_body),
    )
    base_html = _load_base_email_template()
    return (
        base_html
        .replace(HEADER_PLACEHOLDER, rendered_header)
        .replace(BODY_PLACEHOLDER, rendered_body)
        .replace(FOOTER_PLACEHOLDER, rendered_buttons)
    )


def send_email_message(
    *,
    team_id: int,
    recipient: str,
    event_name: str,
    render_context: MessageRenderContext,
) -> None:
    errors = send_email_batch(
        team_id=team_id,
        recipients=[(0, recipient, render_context)],
        event_name=event_name,
    )
    if errors:
        first_error = next(iter(errors.values()))
        raise RuntimeError(first_error)


def _build_email_message(
    *,
    smtp_username: str,
    recipient: str,
    subject: str,
    final_html: str,
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = smtp_username
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content("This email requires an HTML-compatible viewer.")
    message.add_alternative(final_html, subtype="html")
    return message


def send_email_batch(
    *,
    team_id: int,
    recipients: list[tuple[int, str, MessageRenderContext]],
    event_name: str,
) -> dict[int, str]:
    if not recipients:
        return {}

    smtp_config = _load_team_smtp(team_id)
    if smtp_config is None:
        raise RuntimeError("No SMTP configuration for team")

    template = resolve_template(team_id=team_id, channel="email", event_name=event_name)
    if template is None or not bool(template.enable):
        return {}

    smtp_client: smtplib.SMTP | None = None
    recipient_errors: dict[int, str] = {}

    try:
        smtp_client = _open_validated_smtp_client(smtp_config)
        for order_id, raw_recipient, render_context in recipients:
            recipient = raw_recipient.strip()
            if not recipient:
                recipient_errors[order_id] = "Missing email recipient"
                continue

            try:
                subject = _build_subject(template, event_name, render_context)
                final_html = _render_email_html(template.template, render_context)
                logger.debug(
                    "Sending email | team_id=%s order_id=%s recipient=%s event_name=%s subject=%r html_len=%d",
                    team_id,
                    order_id,
                    recipient,
                    event_name,
                    subject,
                    len(final_html),
                )
                message = _build_email_message(
                    smtp_username=smtp_config.smtp_username,
                    recipient=recipient,
                    subject=subject,
                    final_html=final_html,
                )
                rejected_recipients = smtp_client.send_message(message)
                if rejected_recipients:
                    recipient_errors[order_id] = f"SMTP rejected recipients: {rejected_recipients}"
                    logger.warning(
                        "SMTP rejected recipients | order_id=%s recipient=%s details=%s",
                        order_id,
                        recipient,
                        rejected_recipients,
                    )
            except Exception as exc:
                recipient_errors[order_id] = str(exc)
                logger.exception(
                    "Email send failed | team_id=%s order_id=%s recipient=%s event_name=%s",
                    team_id,
                    order_id,
                    recipient,
                    event_name,
                )
    finally:
        if smtp_client is not None:
            try:
                smtp_client.quit()
            except Exception:
                pass

    return recipient_errors
