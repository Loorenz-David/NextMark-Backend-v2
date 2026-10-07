from Delivery_app_BK.services.domain.order.audit import plan_move_changes

OCT_17 = ("2026-10-17T00:00:00+00:00", "2026-10-17T23:59:59+00:00")
OCT_19 = ("2026-10-19T00:00:00+00:00", "2026-10-19T23:59:59+00:00")


def _changes(old_plan_id, new_plan_id, old_dates=(None, None), new_dates=(None, None)):
    return [
        (change.field_name, change.from_value, change.to_value)
        for change in plan_move_changes(
            old_plan_id=old_plan_id,
            new_plan_id=new_plan_id,
            old_plan_start=old_dates[0],
            old_plan_end=old_dates[1],
            new_plan_start=new_dates[0],
            new_plan_end=new_dates[1],
        )
    ]


def test_scheduling_records_the_plan_and_its_delivery_date():
    assert _changes(None, 6, new_dates=OCT_19) == [
        ("route_plan_id", None, 6),
        ("delivery_dates", None, {"start": OCT_19[0], "end": OCT_19[1]}),
    ]


def test_rescheduling_records_the_date_moving():
    assert _changes(5, 6, OCT_17, OCT_19) == [
        ("route_plan_id", 5, 6),
        (
            "delivery_dates",
            {"start": OCT_17[0], "end": OCT_17[1]},
            {"start": OCT_19[0], "end": OCT_19[1]},
        ),
    ]


def test_a_same_day_move_records_only_the_plan():
    assert _changes(5, 6, OCT_17, OCT_17) == [("route_plan_id", 5, 6)]


def test_unscheduling_records_the_plan_left():
    assert _changes(5, None) == [("route_plan_id", 5, None)]
