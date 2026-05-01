from types import SimpleNamespace

from Delivery_app_BK.services.infra.messaging.email_service import _render_email_html
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
