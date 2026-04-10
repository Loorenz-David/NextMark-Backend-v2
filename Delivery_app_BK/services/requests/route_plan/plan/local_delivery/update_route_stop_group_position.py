from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.requests.common.fields import validate_unexpected

ALLOWED_FIELDS = {
    'route_solution_id',
    'route_stop_ids',
    'position',
    'anchor_stop_id',
}

MAX_ROUTE_STOP_IDS = 500


@dataclass(frozen=True)
class RouteStopGroupPositionRequest:
    route_solution_id: int
    route_stop_ids: list[int]
    position: int
    anchor_stop_id: int


def parse_update_route_stop_group_position_request(raw: Any) -> RouteStopGroupPositionRequest:
    if not isinstance(raw, dict):
        raise ValidationFailed('Payload must be an object.')

    validate_unexpected(
        raw,
        ALLOWED_FIELDS,
        context_msg='Unexpected fields in route stop group position payload:',
    )

    route_solution_id = _parse_positive_int(raw.get('route_solution_id'), field='route_solution_id')
    position = _parse_positive_int(raw.get('position'), field='position')
    anchor_stop_id = _parse_positive_int(raw.get('anchor_stop_id'), field='anchor_stop_id')
    route_stop_ids = _parse_route_stop_ids(raw.get('route_stop_ids'))

    return RouteStopGroupPositionRequest(
        route_solution_id=route_solution_id,
        route_stop_ids=route_stop_ids,
        position=position,
        anchor_stop_id=anchor_stop_id,
    )


def _parse_route_stop_ids(value: Any) -> list[int]:
    if not isinstance(value, list):
        raise ValidationFailed('route_stop_ids must be a list of ids.')
    if not value:
        raise ValidationFailed('route_stop_ids must contain at least one id.')
    if len(value) > MAX_ROUTE_STOP_IDS:
        raise ValidationFailed(f'route_stop_ids supports at most {MAX_ROUTE_STOP_IDS} ids.')

    parsed: list[int] = []
    seen: set[int] = set()
    for index, candidate in enumerate(value):
        route_stop_id = _parse_positive_int(candidate, field=f'route_stop_ids[{index}]')
        if route_stop_id in seen:
            continue
        seen.add(route_stop_id)
        parsed.append(route_stop_id)

    if not parsed:
        raise ValidationFailed('route_stop_ids must contain at least one unique id.')

    return parsed


def _parse_positive_int(value: Any, *, field: str) -> int:
    if type(value) is not int:
        raise ValidationFailed(f'{field} must be an integer.')
    if value <= 0:
        raise ValidationFailed(f'{field} must be greater than zero.')
    return value
