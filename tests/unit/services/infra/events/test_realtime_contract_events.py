from Delivery_app_BK.sockets.contracts import realtime


def _business_event_constants() -> dict[str, str]:
    return {
        name: value
        for name, value in vars(realtime).items()
        if name.startswith("BUSINESS_EVENT_") and isinstance(value, str)
    }


def test_realtime_contract_exposes_canonical_route_plan_and_group_events():
    event_constants = _business_event_constants()

    assert event_constants["BUSINESS_EVENT_ROUTE_PLAN_CREATED"] == "route_plan.created"
    assert event_constants["BUSINESS_EVENT_ROUTE_PLAN_UPDATED"] == "route_plan.updated"
    assert event_constants["BUSINESS_EVENT_ROUTE_PLAN_DELETED"] == "route_plan.deleted"
    assert event_constants["BUSINESS_EVENT_ROUTE_GROUP_UPDATED"] == "route_group.updated"


def test_realtime_contract_has_no_legacy_delivery_plan_business_events():
    event_constants = _business_event_constants()

    assert "BUSINESS_EVENT_DELIVERY_PLAN_CREATED" not in event_constants
    assert "BUSINESS_EVENT_DELIVERY_PLAN_UPDATED" not in event_constants
    assert "BUSINESS_EVENT_DELIVERY_PLAN_DELETED" not in event_constants
    assert "BUSINESS_EVENT_LOCAL_DELIVERY_PLAN_UPDATED" not in event_constants

    legacy_values = {
        "delivery_plan.created",
        "delivery_plan.updated",
        "delivery_plan.deleted",
        "local_delivery_plan.updated",
    }
    assert legacy_values.isdisjoint(set(event_constants.values()))
