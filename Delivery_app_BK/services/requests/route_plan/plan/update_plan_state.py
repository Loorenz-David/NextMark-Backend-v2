from dataclasses import dataclass

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.domain.route_operations.plan.plan_states import PlanStateId


VALID_PLAN_STATE_IDS = {
    value
    for key, value in vars(PlanStateId).items()
    if key.isupper() and isinstance(value, int)
}


@dataclass
class PlanStateUpdateRequest:
    plan_ids: list[int]
    state_id: int


def parse_update_plan_state_request(
    plan_ids: int | list[int],
    state_id: int,
) -> PlanStateUpdateRequest:
    parsed_state_id = _parse_state_id(state_id)
    parsed_plan_ids = _parse_plan_ids(plan_ids)
    return PlanStateUpdateRequest(
        plan_ids=parsed_plan_ids,
        state_id=parsed_state_id,
    )


def _parse_state_id(state_id) -> int:
    if isinstance(state_id, bool) or not isinstance(state_id, int):
        raise ValidationFailed("state_id must be an integer.")
    if state_id not in VALID_PLAN_STATE_IDS:
        raise ValidationFailed(f"Invalid state_id '{state_id}' for delivery plans.")
    return state_id


def _parse_plan_ids(plan_ids) -> list[int]:
    if isinstance(plan_ids, bool):
        raise ValidationFailed("plan_ids must be an integer or a list of integers.")
    if isinstance(plan_ids, int):
        return [plan_ids]

    if not isinstance(plan_ids, list):
        raise ValidationFailed("plan_ids must be an integer or a list of integers.")
    if not plan_ids:
        raise ValidationFailed("plan_ids cannot be empty.")

    deduped: list[int] = []
    seen: set[int] = set()
    for value in plan_ids:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValidationFailed("plan_ids must contain integers only.")
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)

    if not deduped:
        raise ValidationFailed("plan_ids cannot be empty.")

    return deduped
