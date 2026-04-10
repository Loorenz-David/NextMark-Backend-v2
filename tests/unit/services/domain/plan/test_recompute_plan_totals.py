from unittest.mock import MagicMock

from Delivery_app_BK.services.domain.route_operations.plan.recompute_plan_totals import (
    recompute_plan_totals,
)


def _make_plan(plan_id=1):
    plan = MagicMock()
    plan.id = plan_id
    plan.total_weight_g = None
    plan.total_volume_cm3 = None
    plan.total_item_count = None
    plan.total_orders = None
    plan.item_type_counts = None
    return plan


def test_item_type_counts_merged_across_orders(monkeypatch):
    plan = _make_plan()

    aggregate_result = [0, 0, 0, 2]
    type_rows = [
        ({"Sofa": 1, "Dining chair": 4},),
        ({"Dining chair": 2, "Lamp": 1},),
    ]

    call_count = [0]

    def side_effect(*args, **kwargs):
        call_count[0] += 1
        m = MagicMock()
        if call_count[0] == 1:
            m.filter.return_value.one.return_value = aggregate_result
        else:
            m.filter.return_value.all.return_value = type_rows
        return m

    monkeypatch.setattr(
        "Delivery_app_BK.services.domain.route_operations.plan.recompute_plan_totals.db.session.query",
        side_effect,
    )

    recompute_plan_totals(plan)

    assert plan.item_type_counts == {"Sofa": 1, "Dining chair": 6, "Lamp": 1}


def test_item_type_counts_none_when_no_orders(monkeypatch):
    plan = _make_plan()

    call_count = [0]

    def side_effect(*args, **kwargs):
        call_count[0] += 1
        m = MagicMock()
        if call_count[0] == 1:
            m.filter.return_value.one.return_value = [None, None, None, 0]
        else:
            m.filter.return_value.all.return_value = []
        return m

    monkeypatch.setattr(
        "Delivery_app_BK.services.domain.route_operations.plan.recompute_plan_totals.db.session.query",
        side_effect,
    )

    recompute_plan_totals(plan)
    assert plan.item_type_counts is None


def test_skips_none_plan():
    recompute_plan_totals(None)
