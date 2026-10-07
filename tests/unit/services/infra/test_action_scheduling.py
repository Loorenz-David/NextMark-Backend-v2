from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from Delivery_app_BK.services.domain.messaging import SCHEDULE_ANCHOR_OCCURRED_AT
from Delivery_app_BK.services.infra.messaging import action_scheduling


@pytest.mark.parametrize(
    ("action_name", "expected_channel", "template_id"),
    [
        ("client_form_submitted_email", "email", 101),
        ("client_form_submitted_sms", "sms", 102),
    ],
)
def test_client_form_submitted_resolves_each_enabled_channel_independently(
    monkeypatch,
    action_name,
    expected_channel,
    template_id,
):
    occurred_at = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)
    event = SimpleNamespace(
        team_id=7,
        event_name="client_form_submitted",
        occurred_at=occurred_at,
    )

    def _resolve_message_template(*, team_id, channel, event_name, plan_type, enabled_only):
        assert team_id == 7
        assert channel == expected_channel
        assert event_name == "client_form_submitted"
        # No order on the event: the resolver still asks for a concrete plan type.
        assert plan_type == "local_delivery"
        assert enabled_only is True
        return SimpleNamespace(
            id=template_id,
            schedule_offset_value=None,
            schedule_offset_unit=None,
        )

    monkeypatch.setattr(
        action_scheduling,
        "resolve_message_template",
        _resolve_message_template,
    )

    schedule = action_scheduling.resolve_order_action_schedule(event, action_name)

    assert schedule is not None
    assert schedule.template_id == template_id
    assert schedule.scheduled_for is None
    assert schedule.schedule_anchor_type == SCHEDULE_ANCHOR_OCCURRED_AT
    assert schedule.schedule_anchor_at == occurred_at


@pytest.mark.parametrize(
    "action_name",
    ["client_form_submitted_email", "client_form_submitted_sms"],
)
def test_client_form_submitted_ignores_channels_without_enabled_template(
    monkeypatch,
    action_name,
):
    event = SimpleNamespace(
        team_id=7,
        event_name="client_form_submitted",
        occurred_at=datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(
        action_scheduling,
        "resolve_message_template",
        lambda **_kwargs: None,
    )

    assert action_scheduling.resolve_order_action_schedule(event, action_name) is None


def test_order_schedule_asks_for_the_template_of_the_orders_plan_type(monkeypatch):
    event = SimpleNamespace(
        team_id=7,
        event_name="order_ready",
        occurred_at=datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc),
        order=SimpleNamespace(
            route_plan=SimpleNamespace(plan_type="store_pickup"),
            order_plan_objective="local_delivery",
        ),
    )
    captured = {}

    def _resolve_message_template(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id=5, schedule_offset_value=None, schedule_offset_unit=None)

    monkeypatch.setattr(action_scheduling, "resolve_message_template", _resolve_message_template)

    schedule = action_scheduling.resolve_order_action_schedule(event, "order_ready_sms")

    assert schedule is not None and schedule.template_id == 5
    assert captured["plan_type"] == "store_pickup"
    assert captured["channel"] == "sms"


def test_route_plan_schedule_asks_for_the_template_of_the_plans_type(monkeypatch):
    event = SimpleNamespace(
        team_id=7,
        event_name="delivery_plan_rescheduled",
        occurred_at=datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc),
        route_plan=SimpleNamespace(plan_type="international_shipping", route_groups=[], start_date=None),
    )
    captured = {}

    def _resolve_message_template(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(action_scheduling, "resolve_message_template", _resolve_message_template)

    assert action_scheduling.resolve_route_plan_action_schedule(event, "plan_delivery_rescheduled_email") is None
    assert captured["plan_type"] == "international_shipping"
    assert captured["channel"] == "email"
    assert captured["enabled_only"] is True
