import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.requests.route_plan.plan.list_route_plans import (
    parse_list_route_plans_query,
)


def test_parse_list_delivery_plans_query_accepts_new_payload_shape():
    parsed = parse_list_route_plans_query(
        query_params={"limit": "10", "label": "legacy"},
        incoming_data={
            "mode": "month",
            "start_date": "2026-03-01",
            "end_date": "2026-03-31",
            "filters": {
                "plan_type": "local_delivery",
                "max_orders": 50,
            },
            "after_cursor": "opaque-token",
        },
    )

    assert parsed["covers_start"] == "2026-03-01"
    assert parsed["covers_end"] == "2026-03-31"
    assert parsed["plan_type"] == "local_delivery"
    assert parsed["max_orders"] == 50
    assert parsed["after_cursor"] == "opaque-token"
    assert parsed["limit"] == "10"


def test_parse_list_delivery_plans_query_payload_overrides_legacy_filters():
    parsed = parse_list_route_plans_query(
        query_params={"plan_type": "regional"},
        incoming_data={
            "mode": "range",
            "start_date": "2026-03-10",
            "end_date": "2026-03-15",
            "filters": {"plan_type": "local_delivery"},
        },
    )

    assert parsed["plan_type"] == "local_delivery"


def test_parse_list_delivery_plans_query_supports_legacy_only_shape():
    parsed = parse_list_route_plans_query(
        query_params={"label": "March", "limit": "25"},
        incoming_data=None,
    )

    assert parsed == {"label": "March", "limit": "25"}


def test_parse_list_delivery_plans_query_rejects_non_object_payload():
    with pytest.raises(ValidationFailed):
        parse_list_route_plans_query(
            query_params={},
            incoming_data=["invalid"],
        )


def test_parse_list_delivery_plans_query_rejects_invalid_mode():
    with pytest.raises(ValidationFailed):
        parse_list_route_plans_query(
            query_params={},
            incoming_data={
                "mode": "week",
                "start_date": "2026-03-01",
                "end_date": "2026-03-02",
            },
        )


def test_parse_list_delivery_plans_query_rejects_missing_dates_when_mode_present():
    with pytest.raises(ValidationFailed):
        parse_list_route_plans_query(
            query_params={},
            incoming_data={
                "mode": "date",
                "start_date": "2026-03-01",
            },
        )


def test_parse_list_delivery_plans_query_rejects_non_object_filters():
    with pytest.raises(ValidationFailed):
        parse_list_route_plans_query(
            query_params={},
            incoming_data={
                "mode": "range",
                "start_date": "2026-03-01",
                "end_date": "2026-03-31",
                "filters": "invalid",
            },
        )


def test_parse_list_delivery_plans_query_rejects_pagination_keys_inside_filters():
    with pytest.raises(ValidationFailed):
        parse_list_route_plans_query(
            query_params={},
            incoming_data={
                "mode": "range",
                "start_date": "2026-03-01",
                "end_date": "2026-03-31",
                "filters": {"limit": 50},
            },
        )
