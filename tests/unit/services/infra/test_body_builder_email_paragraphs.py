from types import SimpleNamespace

from Delivery_app_BK.services.infra.messaging.body_builder import build_message_body
from Delivery_app_BK.services.infra.messaging.label_resolvers import MessageRenderContext


def test_build_message_body_email_separates_paragraphs_with_html_breaks():
    context = MessageRenderContext(order=SimpleNamespace(client_first_name="Alice"))

    rendered = build_message_body(
        [
            {
                "type": "paragraph",
                "children": [
                    {"text": "the expected time of arrival is "},
                    {
                        "type": "label",
                        "children": [{"text": ""}],
                        "labelKey": "client_first_name",
                    },
                ],
            },
            {
                "type": "paragraph",
                "children": [{"text": "test paragraph"}],
            },
        ],
        context,
        channel="email",
    )

    assert rendered == "the expected time of arrival is Alice<br><br>test paragraph"


def test_build_message_body_sms_keeps_plaintext_newlines():
    context = MessageRenderContext(order=SimpleNamespace(client_first_name="Alice"))

    rendered = build_message_body(
        [
            {
                "type": "paragraph",
                "children": [{"text": "first line"}],
            },
            {
                "type": "paragraph",
                "children": [{"text": "second line"}],
            },
        ],
        context,
        channel="sms",
    )

    assert rendered == "first line\nsecond line"
