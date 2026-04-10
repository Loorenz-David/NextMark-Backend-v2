import pytest

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.domain.route_operations.plan.plan_states import PlanStateId
from Delivery_app_BK.services.requests.route_plan.plan.update_plan_state import (
    parse_update_plan_state_request,
)


def test_parse_update_plan_state_request_accepts_single_plan_id():
    result = parse_update_plan_state_request(10, PlanStateId.READY)
    assert result.plan_ids == [10]
    assert result.state_id == PlanStateId.READY


def test_parse_update_plan_state_request_dedupes_plan_ids():
    result = parse_update_plan_state_request([4, 4, 5], PlanStateId.PROCESSING)
    assert result.plan_ids == [4, 5]


def test_parse_update_plan_state_request_rejects_invalid_state_id():
    with pytest.raises(ValidationFailed):
        parse_update_plan_state_request(10, 999)


def test_parse_update_plan_state_request_rejects_non_int_plan_ids():
    with pytest.raises(ValidationFailed):
        parse_update_plan_state_request([1, "2"], PlanStateId.READY)


def test_parse_update_plan_state_request_rejects_empty_plan_ids():
    with pytest.raises(ValidationFailed):
        parse_update_plan_state_request([], PlanStateId.READY)
