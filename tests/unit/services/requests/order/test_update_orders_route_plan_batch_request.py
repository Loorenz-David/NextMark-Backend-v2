import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.requests.order.update_orders_route_plan_batch import (
    MAX_MANUAL_IDS,
    parse_update_orders_route_plan_batch_payload,
)


def test_parse_batch_selection_payload_accepts_valid_payload():
    parsed = parse_update_orders_route_plan_batch_payload(
        {
            "selection": {
                "manual_order_ids": [5, 2, 5, 1],
                "excluded_order_ids": [9, 9],
                "select_all_snapshots": [
                    {
                        "query": {
                            "q": " abc ",
                            "show_archived": True,
                            "s": ["client_email", "client_email"],
                        }
                    }
                ],
            }
        }
    )

    assert parsed.manual_order_ids == [5, 2, 1]
    assert parsed.excluded_order_ids == [9]
    assert len(parsed.select_all_snapshots) == 1
    assert parsed.select_all_snapshots[0].query["q"] == "abc"
    assert parsed.select_all_snapshots[0].query["s"] == ["client_email"]
    assert parsed.signature


def test_parse_batch_selection_payload_rejects_bool_ids():
    with pytest.raises(ValidationFailed):
        parse_update_orders_route_plan_batch_payload(
            {
                "selection": {
                    "manual_order_ids": [True],  # type: ignore[list-item]
                    "select_all_snapshots": [],
                    "excluded_order_ids": [],
                }
            }
        )


def test_parse_batch_selection_payload_rejects_too_many_manual_ids():
    with pytest.raises(ValidationFailed):
        parse_update_orders_route_plan_batch_payload(
            {
                "selection": {
                    "manual_order_ids": list(range(1, MAX_MANUAL_IDS + 2)),
                    "select_all_snapshots": [],
                    "excluded_order_ids": [],
                }
            }
        )


def test_parse_batch_selection_payload_rejects_unknown_query_filters():
    with pytest.raises(ValidationFailed):
        parse_update_orders_route_plan_batch_payload(
            {
                "selection": {
                    "manual_order_ids": [],
                    "excluded_order_ids": [],
                    "select_all_snapshots": [
                        {
                            "query": {
                                "q": "ref",
                                "unknown_filter": "x",
                            }
                        }
                    ],
                }
            }
        )


def test_parse_batch_selection_payload_dedupes_identical_snapshots():
    parsed = parse_update_orders_route_plan_batch_payload(
        {
            "selection": {
                "manual_order_ids": [],
                "excluded_order_ids": [],
                "select_all_snapshots": [
                    {"query": {"q": "abc", "show_archived": True}},
                    {"query": {"show_archived": True, "q": "abc"}},
                ],
            }
        }
    )

    assert len(parsed.select_all_snapshots) == 1


def test_parse_batch_selection_payload_accepts_route_plan_id_alias():
    parsed = parse_update_orders_route_plan_batch_payload(
        {
            "selection": {
                "manual_order_ids": [],
                "excluded_order_ids": [],
                "select_all_snapshots": [
                    {
                        "query": {
                            "route_plan_id": 42,
                        }
                    }
                ],
            }
        }
    )

    assert parsed.select_all_snapshots[0].query["route_plan_id"] == 42


def test_parse_batch_selection_payload_rejects_mismatched_plan_aliases():
    with pytest.raises(ValidationFailed):
        parse_update_orders_route_plan_batch_payload(
            {
                "selection": {
                    "manual_order_ids": [],
                    "excluded_order_ids": [],
                    "select_all_snapshots": [
                        {
                            "query": {
                                "route_plan_id": 42,
                                "delivery_plan_id": 43,
                            }
                        }
                    ],
                }
            }
        )
