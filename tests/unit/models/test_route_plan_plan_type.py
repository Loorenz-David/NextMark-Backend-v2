from __future__ import annotations

import pytest

from Delivery_app_BK.models import RoutePlan


def test_plan_type_accepts_every_planning_domain():
    for plan_type in ("local_delivery", "international_shipping", "store_pickup"):
        plan = RoutePlan()
        plan.plan_type = plan_type
        assert plan.plan_type == plan_type


def test_plan_type_rejects_unknown_value():
    plan = RoutePlan()

    with pytest.raises(ValueError):
        plan.plan_type = "route_operations"


def test_plan_type_rejects_none():
    # The column is non-nullable; a None assignment must fail loudly at the model
    # rather than surfacing as an IntegrityError at flush time.
    plan = RoutePlan()

    with pytest.raises(ValueError):
        plan.plan_type = None


def test_route_plan_owns_its_type_specific_children():
    relationships = {rel.key for rel in RoutePlan.__mapper__.relationships}

    assert "international_shipping_plan" in relationships
    assert "store_pickup_plan" in relationships
