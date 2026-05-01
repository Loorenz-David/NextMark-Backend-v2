import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models.tables.content_templates.message_template import MessageTemplate


def test_message_template_normalizes_legacy_footer_buttons_key():
    template = MessageTemplate()

    template.template = {
        "header": [],
        "body": [],
        "footer_buttons": [
            {
                "label": "Tracking page",
                "url": "tracking_link",
            }
        ],
    }

    assert template.template["footerButtons"] == [
        {
            "label": "Tracking page",
            "url": "tracking_link",
        }
    ]


def test_message_template_copies_template_payload_on_assignment():
    template = MessageTemplate()
    payload = {
        "header": [],
        "body": [],
        "footerButtons": [],
    }

    template.template = payload
    payload["footerButtons"].append({"label": "Late mutation", "urlTemplate": "tracking_link"})

    assert template.template["footerButtons"] == []


def test_message_template_accepts_list_template_payload():
    template = MessageTemplate()

    payload = [{"type": "paragraph", "children": [{"text": "sms body"}]}]
    template.template = payload
    payload.append({"type": "paragraph", "children": [{"text": "mutated later"}]})

    assert template.template == [{"type": "paragraph", "children": [{"text": "sms body"}]}]


def test_message_template_rejects_non_json_template_payload():
    template = MessageTemplate()

    with pytest.raises(ValidationFailed, match="Invalid template payload"):
        template.template = "not-json"
