import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models.tables.content_templates.message_template import MessageTemplate
from Delivery_app_BK.services.domain.order.order_events import OrderEvent


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


def test_message_template_copies_subject_payload_on_assignment():
    template = MessageTemplate()
    payload = [{"type": "label", "labelKey": "client_first_name"}]

    template.subject = payload
    payload.append({"text": " mutated later"})

    assert template.subject == [{"type": "label", "labelKey": "client_first_name"}]


def test_message_template_accepts_plain_string_subject():
    template = MessageTemplate()

    template.subject = "Delivery update for {{ client_first_name }}"

    assert template.subject == "Delivery update for {{ client_first_name }}"


def test_message_template_rejects_invalid_subject_payload():
    template = MessageTemplate()

    with pytest.raises(ValidationFailed, match="Invalid subject payload"):
        template.subject = 123


def test_message_template_accepts_client_form_submitted_event():
    template = MessageTemplate()

    template.event = OrderEvent.CLIENT_FORM_SUBMITTED.value

    assert template.event == "client_form_submitted"


@pytest.mark.parametrize("plan_type", ["local_delivery", "store_pickup", "international_shipping"])
def test_message_template_accepts_every_planning_domain(plan_type):
    template = MessageTemplate()

    template.plan_type = plan_type

    assert template.plan_type == plan_type


def test_message_template_rejects_unknown_plan_type():
    template = MessageTemplate()

    with pytest.raises(ValidationFailed, match="Invalid plan_type"):
        template.plan_type = "pickup"


def test_message_template_rejects_none_plan_type():
    template = MessageTemplate()

    with pytest.raises(ValidationFailed, match="Invalid plan_type"):
        template.plan_type = None


def test_message_template_is_unique_per_team_event_channel_and_plan_type():
    constraint = next(
        c
        for c in MessageTemplate.__table__.constraints
        if c.name == "uq_message_template_team_event_channel_plan_type"
    )

    assert [column.name for column in constraint.columns] == ["team_id", "event", "channel", "plan_type"]
    assert not any(c.name == "uq_message_template_team_event_channel" for c in MessageTemplate.__table__.constraints)
