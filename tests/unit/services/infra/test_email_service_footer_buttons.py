from types import SimpleNamespace

from Delivery_app_BK.services.infra.messaging.email_service import _build_subject, _render_email_html
from Delivery_app_BK.services.infra.messaging.label_resolvers import MessageRenderContext


BASE_TEMPLATE = """{{HEADER_CONTENT}}\n{{BODY_CONTENT}}\n{{FOOTER_BUTTONS}}"""


def test_render_email_html_renders_footer_button_from_footer_buttons(monkeypatch):
    monkeypatch.setattr(
        "Delivery_app_BK.services.infra.messaging.email_service._load_base_email_template",
        lambda: BASE_TEMPLATE,
    )
    context = MessageRenderContext(
        order=SimpleNamespace(tracking_link="https://track.nextmark.app/t/abc123"),
    )

    html = _render_email_html(
        {
            "header": ["Track your order"],
            "body": ["Open the page below."],
            "footerButtons": [
                {
                    "label": "Track order",
                    "urlTemplate": "tracking_link",
                }
            ],
        },
        context,
    )

    assert 'href="https://track.nextmark.app/t/abc123"' in html
    assert "Track order" in html


def test_render_email_html_renders_footer_button_from_legacy_footer_shape(monkeypatch):
    monkeypatch.setattr(
        "Delivery_app_BK.services.infra.messaging.email_service._load_base_email_template",
        lambda: BASE_TEMPLATE,
    )
    context = MessageRenderContext(
        order=SimpleNamespace(),
        extra_context={"client_form_link": "https://forms.nextmark.app/form/token123"},
    )

    html = _render_email_html(
        {
            "header": ["Complete your form"],
            "body": ["Use the link below."],
            "footer_buttons": {
                "text": "Open form",
                "url": "client_form_link",
            },
        },
        context,
    )

    assert 'href="https://forms.nextmark.app/form/token123"' in html
    assert "Open form" in html


def test_build_subject_renders_structured_label_subject():
    context = MessageRenderContext(
        order=SimpleNamespace(client_first_name="Anna", tracking_number="NM-42"),
    )
    template = SimpleNamespace(
        subject=[
            {
                "type": "paragraph",
                "children": [
                    {"text": "Delivery update for "},
                    {"type": "label", "labelKey": "client_first_name"},
                    {"text": " / "},
                    {"type": "label", "labelKey": "tracking_number"},
                ],
            }
        ],
        name="Fallback name",
    )

    subject = _build_subject(template, "order_processing", context)

    assert subject == "Delivery update for Anna / NM-42"


def test_build_subject_renders_string_label_subject():
    context = MessageRenderContext(order=SimpleNamespace(client_first_name="Anna"))
    template = SimpleNamespace(
        subject="Delivery update for {{ client_first_name }}",
        name="Fallback name",
    )

    subject = _build_subject(template, "order_processing", context)

    assert subject == "Delivery update for Anna"


def test_build_subject_falls_back_when_subject_empty():
    context = MessageRenderContext(order=SimpleNamespace())
    template = SimpleNamespace(subject=None, name="Fallback name")

    subject = _build_subject(template, "order_processing", context)

    assert subject == "Fallback name"
