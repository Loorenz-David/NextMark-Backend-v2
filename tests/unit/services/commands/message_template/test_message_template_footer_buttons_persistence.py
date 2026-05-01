from types import SimpleNamespace

from Delivery_app_BK.services.commands.message_template.create_message_template import create_message_template
from Delivery_app_BK.services.commands.message_template.update_message_template import update_message_template
from Delivery_app_BK.services.context import ServiceContext


class DummyTemplate:
    id = 7
    event = "order_processing"
    schedule_offset_value = None
    schedule_offset_unit = None
    template = {
        "header": [],
        "body": [],
        "footerButtons": [],
    }


def test_create_message_template_preserves_footer_buttons(monkeypatch):
    captured = {}

    def fake_create_instance(ctx, model, fields):
        captured["template"] = fields["template"]
        return SimpleNamespace(
            id=7,
            event=fields["event"],
            schedule_offset_value=fields.get("schedule_offset_value"),
            schedule_offset_unit=fields.get("schedule_offset_unit"),
        )

    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.message_template.create_message_template.create_instance",
        fake_create_instance,
    )
    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.message_template.create_message_template.validate_schedule_configuration",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.message_template.create_message_template.build_create_result",
        lambda ctx, instances: instances,
    )
    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.message_template.create_message_template.db.session.add_all",
        lambda instances: None,
    )
    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.message_template.create_message_template.db.session.flush",
        lambda: None,
    )
    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.message_template.create_message_template.db.session.commit",
        lambda: None,
    )

    ctx = ServiceContext(
        incoming_data={
            "fields": {
                "client_id": "message_template_1",
                "name": "Out for delivery",
                "event": "order_processing",
                "enable": True,
                "ask_permission": False,
                "template": {
                    "header": [],
                    "body": [],
                    "footerButtons": [
                        {
                            "id": "btn-1",
                            "label": "Tracking page",
                            "urlTemplate": "tracking_link",
                        }
                    ],
                },
                "channel": "email",
                "schedule_offset_value": None,
                "schedule_offset_unit": None,
            }
        }
    )

    create_message_template(ctx)

    assert captured["template"]["footerButtons"] == [
        {
            "id": "btn-1",
            "label": "Tracking page",
            "urlTemplate": "tracking_link",
        }
    ]


def test_update_message_template_preserves_footer_buttons(monkeypatch):
    template = DummyTemplate()
    captured = {}

    def fake_update_instance(ctx, model, fields, target_id):
        captured["template"] = fields["template"]
        template.template = fields["template"]
        return template

    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.message_template.update_message_template.update_instance",
        fake_update_instance,
    )
    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.message_template.update_message_template.validate_schedule_configuration",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "Delivery_app_BK.services.commands.message_template.update_message_template.db.session.commit",
        lambda: None,
    )

    ctx = ServiceContext(
        incoming_data={
            "target": {
                "target_id": 7,
                "fields": {
                    "template": {
                        "header": [],
                        "body": [],
                        "footerButtons": [
                            {
                                "id": "btn-1",
                                "label": "Tracking page",
                                "urlTemplate": "tracking_link",
                            }
                        ],
                    }
                },
            }
        }
    )

    update_message_template(ctx)

    assert captured["template"]["footerButtons"] == [
        {
            "id": "btn-1",
            "label": "Tracking page",
            "urlTemplate": "tracking_link",
        }
    ]
