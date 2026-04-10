from __future__ import annotations

from typing import Any

from Delivery_app_BK.errors import ValidationFailed


ALLOWED_TIME_MODES = {"month", "date", "range"}
PAGINATION_KEYS = {"after_cursor", "before_cursor", "limit", "sort"}


def parse_list_route_plans_query(
    query_params: Any,
    incoming_data: Any,
) -> dict[str, Any]:
    normalized = _to_plain_dict(query_params)

    query_mode = normalized.get("mode")
    query_has_dates = (
        "start_date" in normalized or
        "end_date" in normalized
    )

    if query_mode is not None:
        if not isinstance(query_mode, str) or query_mode not in ALLOWED_TIME_MODES:
            raise ValidationFailed("mode must be one of: month, date, range.")

    if query_mode is not None or query_has_dates:
        start_date = _require_non_empty_string(
            normalized.get("start_date"),
            field="start_date",
        )
        end_date = _require_non_empty_string(
            normalized.get("end_date"),
            field="end_date",
        )
        normalized["covers_start"] = start_date
        normalized["covers_end"] = end_date
        normalized.pop("start_date", None)
        normalized.pop("end_date", None)
        normalized.pop("mode", None)

    if incoming_data is None:
        return normalized

    if not isinstance(incoming_data, dict):
        raise ValidationFailed("List plans payload must be an object.")

    mode = incoming_data.get("mode")
    has_payload_dates = (
        "start_date" in incoming_data or
        "end_date" in incoming_data
    )

    if mode is not None:
        if not isinstance(mode, str) or mode not in ALLOWED_TIME_MODES:
            raise ValidationFailed("mode must be one of: month, date, range.")

    if mode is not None or has_payload_dates:
        start_date = _require_non_empty_string(
            incoming_data.get("start_date"),
            field="start_date",
        )
        end_date = _require_non_empty_string(
            incoming_data.get("end_date"),
            field="end_date",
        )

        # New payload time filter maps to overlap semantics.
        normalized["covers_start"] = start_date
        normalized["covers_end"] = end_date
        normalized.pop("start_date", None)
        normalized.pop("end_date", None)
        normalized.pop("mode", None)

    filters = incoming_data.get("filters")
    if filters is not None:
        if not isinstance(filters, dict):
            raise ValidationFailed("filters must be an object.")

        forbidden = sorted(set(filters.keys()) & PAGINATION_KEYS)
        if forbidden:
            raise ValidationFailed(
                f"filters contains unsupported pagination keys: {forbidden}."
            )

        normalized.update(filters)

    for key, value in incoming_data.items():
        if key in {"mode", "start_date", "end_date", "filters"}:
            continue
        normalized[key] = value

    return normalized


def _to_plain_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}

    if isinstance(value, dict):
        return dict(value)

    if hasattr(value, "items"):
        return dict(value.items())

    return dict(value)


def _require_non_empty_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValidationFailed(f"{field} must be a non-empty string.")

    trimmed = value.strip()
    if not trimmed:
        raise ValidationFailed(f"{field} must be a non-empty string.")

    return trimmed
