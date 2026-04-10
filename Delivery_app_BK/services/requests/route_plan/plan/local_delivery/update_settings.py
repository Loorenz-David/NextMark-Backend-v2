from dataclasses import dataclass
from datetime import datetime

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.requests.common.datetime import (
    normalize_end_date,
    normalize_start_date,
    parse_datetime_utc,
)
from Delivery_app_BK.services.requests.common.fields import validate_unexpected
from Delivery_app_BK.services.requests.common.types import (
    parse_optional_time_zone,
    validate_str,
)
from Delivery_app_BK.services.domain.route_operations.local_delivery import (
    normalize_service_time_payload,
)


ALLOWED_TOP_LEVEL_FIELDS = {
    "route_group_id",
    "route_plan",
    "route_group",
    "route_solution",
    "create_variant_on_save",
    "time_zone",
}

ALLOWED_ROUTE_GROUP_FIELDS: set[str] = set()


@dataclass
class RoutePlanPatchRequest:
    label: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    has_label: bool = False
    has_start_date: bool = False
    has_end_date: bool = False


@dataclass
class RouteGroupPatchRequest:
    pass


@dataclass
class RouteSolutionPatchRequest:
    route_solution_id: int | str | None = None
    start_location: dict | None = None
    end_location: dict | None = None
    set_start_time: str | None = None
    set_end_time: str | None = None
    eta_tolerance_seconds: int = 0
    eta_message_tolerance: int | None = None
    route_end_strategy: str | None = None
    driver_id: int | None = None
    vehicle_id: int | None = None
    stops_service_time: dict | None = None
    has_start_location: bool = False
    has_end_location: bool = False
    has_set_start_time: bool = False
    has_set_end_time: bool = False
    has_eta_tolerance_seconds: bool = False
    has_eta_message_tolerance: bool = False
    has_route_end_strategy: bool = False
    has_driver_id: bool = False
    has_vehicle_id: bool = False
    has_stops_service_time: bool = False


@dataclass
class RouteGroupSettingsRequest:
    route_group_id: int | str
    route_plan: RoutePlanPatchRequest
    route_group: RouteGroupPatchRequest
    route_solution: RouteSolutionPatchRequest
    create_variant_on_save: bool
    time_zone: str | None


def parse_update_local_delivery_settings_request(raw: dict) -> RouteGroupSettingsRequest:
    if not isinstance(raw, dict):
        raise ValidationFailed("Payload must be an object.")
    
    validate_unexpected(
        raw,
        ALLOWED_TOP_LEVEL_FIELDS,
        context_msg="Unexpected fields in local delivery settings payload:",
    )

    route_group_id = _validate_identifier(
        raw.get("route_group_id"),
        field="route_group_id",
    )

    delivery_plan_raw = _as_dict(raw.get("route_plan"), field="route_plan")
    local_delivery_raw = _as_dict(raw.get("route_group"), field="route_group")
    route_solution_raw = _as_dict(raw.get("route_solution"), field="route_solution")

    route_solution_id = (
        route_solution_raw.get("id")
        or route_solution_raw.get("route_solution_id")
    )
    route_solution_id = _validate_identifier(
        route_solution_id,
        field="route_solution id",
    )

    route_plan_patch = _parse_route_plan_patch(delivery_plan_raw)
    route_group_patch = _parse_route_group_patch(local_delivery_raw)
    route_solution_patch = _parse_route_solution_patch(
        route_solution_id=route_solution_id,
        route_solution_raw=route_solution_raw,
    )

    if (
        route_plan_patch.has_start_date
        and route_plan_patch.has_end_date
        and route_plan_patch.start_date is not None
        and route_plan_patch.end_date is not None
        and route_plan_patch.end_date < route_plan_patch.start_date
    ):
        raise ValidationFailed("route plan end date cannot be before start date.")

    time_zone = _parse_time_zone(raw.get("time_zone"))
    create_variant_on_save = bool(raw.get("create_variant_on_save"))

    return RouteGroupSettingsRequest(
        route_group_id=route_group_id,
        route_plan=route_plan_patch,
        route_group=route_group_patch,
        route_solution=route_solution_patch,
        create_variant_on_save=create_variant_on_save,
        time_zone=time_zone,
    )


def parse_update_route_group_settings_request(raw: dict) -> RouteGroupSettingsRequest:
    return parse_update_local_delivery_settings_request(raw)


def _parse_route_plan_patch(raw: dict) -> RoutePlanPatchRequest:
    patch = RoutePlanPatchRequest()

    if "label" in raw:
        patch.has_label = True
        patch.label = validate_str(raw.get("label"), field="route_plan.label")

    if "start_date" in raw:
        patch.has_start_date = True
        if raw.get("start_date") is not None:
            patch.start_date = normalize_start_date(raw.get("start_date"))

    if "end_date" in raw:
        patch.has_end_date = True
        if raw.get("end_date") is not None:
            patch.end_date = normalize_end_date(raw.get("end_date"))

    return patch


def _parse_route_group_patch(raw: dict) -> RouteGroupPatchRequest:
    validate_unexpected(
        raw,
        ALLOWED_ROUTE_GROUP_FIELDS,
        context_msg="Unexpected fields in route_group payload:",
    )
    patch = RouteGroupPatchRequest()
    return patch


def _parse_route_solution_patch(
    route_solution_id: int | str,
    route_solution_raw: dict,
) -> RouteSolutionPatchRequest:
    patch = RouteSolutionPatchRequest(route_solution_id=route_solution_id)

    if "start_location" in route_solution_raw:
        patch.has_start_location = True
        patch.start_location = _validate_nullable_location(
            route_solution_raw.get("start_location"),
            field="route_solution.start_location",
        )

    if "end_location" in route_solution_raw:
        patch.has_end_location = True
        patch.end_location = _validate_nullable_location(
            route_solution_raw.get("end_location"),
            field="route_solution.end_location",
        )

    if "set_start_time" in route_solution_raw:
        patch.has_set_start_time = True
        patch.set_start_time = _normalize_nullable_time_string(
            route_solution_raw.get("set_start_time")
        )

    if "set_end_time" in route_solution_raw:
        patch.has_set_end_time = True
        patch.set_end_time = _normalize_nullable_time_string(
            route_solution_raw.get("set_end_time")
        )

    if "eta_tolerance_minutes" in route_solution_raw:
        patch.has_eta_tolerance_seconds = True
        patch.eta_tolerance_seconds = _validate_eta_tolerance_seconds_from_minutes(
            route_solution_raw.get("eta_tolerance_minutes"),
            field="route_solution.eta_tolerance_minutes",
        )

    if "eta_message_tolerance" in route_solution_raw:
        patch.has_eta_message_tolerance = True
        patch.eta_message_tolerance = _validate_eta_tolerance_seconds(
            route_solution_raw.get("eta_message_tolerance"),
            field="route_solution.eta_message_tolerance",
        )

    if "route_end_strategy" in route_solution_raw:
        patch.has_route_end_strategy = True
        value = route_solution_raw.get("route_end_strategy")
        patch.route_end_strategy = (
            validate_str(value, field="route_solution.route_end_strategy")
            if value is not None
            else None
        )

    if "driver_id" in route_solution_raw:
        patch.has_driver_id = True
        patch.driver_id = _validate_nullable_int(
            route_solution_raw.get("driver_id"),
            field="route_solution.driver_id",
        )

    if "vehicle_id" in route_solution_raw:
        patch.has_vehicle_id = True
        patch.vehicle_id = _validate_nullable_int(
            route_solution_raw.get("vehicle_id"),
            field="route_solution.vehicle_id",
        )

    if "stops_service_time" in route_solution_raw:
        patch.has_stops_service_time = True
        patch.stops_service_time = normalize_service_time_payload(
            route_solution_raw.get("stops_service_time"),
            field="route_solution.stops_service_time",
            strict=True,
        )

    return patch


def _as_dict(value, *, field: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValidationFailed(f"{field} must be an object.")
    return value


def _validate_identifier(value, *, field: str) -> int | str:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip()
        if normalized:
            return normalized
    raise ValidationFailed(f"{field} is required.")


def _validate_nullable_int(value, *, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise ValidationFailed(f"{field} must be an integer.")


def _validate_eta_tolerance_seconds_from_minutes(value, *, field: str) -> int:
    if value is None:
        return 0
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationFailed(f"{field} must be an integer.")
    seconds = value * 60
    if seconds < 0 or seconds > 7200:
        raise ValidationFailed(f"{field} must be between 0 and 120 minutes.")
    return seconds


def _validate_eta_tolerance_seconds(value, *, field: str) -> int:
    if value is None:
        return 1800
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationFailed(f"{field} must be an integer.")
    if value < 0 or value > 7200:
        raise ValidationFailed(f"{field} must be between 0 and 7200.")
    return value


def _validate_nullable_datetime(value, *, field: str) -> datetime | None:
    if value is None:
        return None
    parsed = parse_datetime_utc(value)
    if not parsed:
        raise ValidationFailed(f"{field} must be a valid date.")
    return parsed


def _validate_nullable_location(value, *, field: str) -> dict | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    raise ValidationFailed(f"{field} must be an object.")


def _normalize_nullable_time_string(value) -> str | None:
    if value is None:
        return None
    parsed = str(value).strip()
    if not parsed:
        return None
    return parsed


def _parse_time_zone(value) -> str | None:
    return parse_optional_time_zone(value, field="time_zone")
