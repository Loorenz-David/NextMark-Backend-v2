from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from Delivery_app_BK.models import RoutePlan
from Delivery_app_BK.services.plan_types import get_plan_type_module


def test_every_plan_type_has_a_registered_module():
    # A plan type without a module would silently skip every hook for its orders.
    for plan_type in RoutePlan.PLAN_TYPES:
        plan_type_module = get_plan_type_module(plan_type)

        assert plan_type_module is not None, plan_type
        assert plan_type_module.plan_type == plan_type


def test_unknown_or_missing_plan_type_resolves_to_no_module():
    assert get_plan_type_module(None) is None
    assert get_plan_type_module("unknown") is None


def test_only_local_delivery_adds_route_freshness_to_order_realtime_payloads():
    # Non-local orders used to carry route freshness too, which sent the admin app
    # after a route context that cannot exist for them.
    route_plan = SimpleNamespace(updated_at=datetime(2026, 10, 7, tzinfo=timezone.utc))

    assert get_plan_type_module("local_delivery").build_order_realtime_extras(route_plan) == {
        "route_freshness_updated_at": "2026-10-07T00:00:00+00:00",
    }
    for plan_type in ("store_pickup", "international_shipping"):
        assert get_plan_type_module(plan_type).build_order_realtime_extras(route_plan) == {}
