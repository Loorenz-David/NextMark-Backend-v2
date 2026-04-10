from datetime import datetime, timezone
from types import MethodType, SimpleNamespace

from Delivery_app_BK.services.infra.messaging.label_resolvers import (
    MessageRenderContext,
    resolve_label,
)


def test_resolve_expected_arrival_time_costumer_uses_route_solution_tolerance():
    context = MessageRenderContext(order=SimpleNamespace(id=42), team_time_zone="UTC")
    stop = SimpleNamespace(
        expected_arrival_time=datetime(2026, 4, 10, 12, 10, tzinfo=timezone.utc)
    )
    route_solution = SimpleNamespace(eta_message_tolerance=2400)
    context.get_selected_route_stop = MethodType(lambda self: stop, context)
    context.get_selected_route_solution = MethodType(lambda self: route_solution, context)

    rendered = resolve_label("expected_arrival_time_costumer", context, channel="sms")

    assert rendered == "2026-04-10 11:20 to 2026-04-10 12:40"


def test_resolve_expected_arrival_time_costumer_defaults_to_thirty_minutes():
    context = MessageRenderContext(order=SimpleNamespace(id=42), team_time_zone="UTC")
    stop = SimpleNamespace(
        expected_arrival_time=datetime(2026, 4, 10, 12, 10, tzinfo=timezone.utc)
    )
    route_solution = SimpleNamespace(eta_message_tolerance=None)
    context.get_selected_route_stop = MethodType(lambda self: stop, context)
    context.get_selected_route_solution = MethodType(lambda self: route_solution, context)

    rendered = resolve_label("expected_arrival_time_costumer", context, channel="sms")

    assert rendered == "2026-04-10 11:30 to 2026-04-10 12:30"


def test_old_eta_range_label_no_longer_resolves():
    context = MessageRenderContext(order=SimpleNamespace(id=42))

    assert resolve_label("expected_arrival_time_with_range_30", context, channel="sms") == ""


def test_resolve_expected_arrival_time_costumer_uses_team_time_zone_before_rounding():
    context = MessageRenderContext(
        order=SimpleNamespace(id=42),
        team_time_zone="Europe/Stockholm",
    )
    stop = SimpleNamespace(
        expected_arrival_time=datetime(2026, 4, 10, 12, 10, tzinfo=timezone.utc)
    )
    route_solution = SimpleNamespace(eta_message_tolerance=1800)
    context.get_selected_route_stop = MethodType(lambda self: stop, context)
    context.get_selected_route_solution = MethodType(lambda self: route_solution, context)

    rendered = resolve_label("expected_arrival_time_costumer", context, channel="sms")

    assert rendered == "2026-04-10 13:30 to 2026-04-10 14:30"
