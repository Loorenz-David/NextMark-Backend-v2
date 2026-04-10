from datetime import datetime
from jsonschema import validate
from jsonschema.exceptions import ValidationError

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models.schemas.time_warning_schema import TIME_WARNING_SCHEMA


class TimeWarningFactory:
    """
    Factory for generating validated time-related warnings.
    """

    @staticmethod
    def _validate_warning(warning: dict) -> dict:
        try:
            validate(instance=warning, schema=TIME_WARNING_SCHEMA)
        except ValidationError as e:
            raise ValidationFailed(f"Invalid time warning schema: {e.message}")
        return warning

    @staticmethod
    def time_window_violation(
        expected_time: datetime,
        window_start: datetime,
        window_end: datetime
    ) -> dict:
        return TimeWarningFactory._validate_warning({
            "type": "time_window_violation",
            "severity": "error",
            "message": "Arrival time is outside the allowed time window",
            "expected_time": expected_time.isoformat(),
            "allowed_start": window_start.isoformat(),
            "allowed_end": window_end.isoformat()
        })

    @staticmethod
    def route_end_time_exceeded(
        expected_end: datetime,
        allowed_end: datetime
    ) -> dict:
        return TimeWarningFactory._validate_warning({
            "type": "route_end_time_exceeded",
            "severity": "error",
            "message": "Route ends after allowed end time",
            "route_expected_end": expected_end.isoformat(),
            "route_allowed_end": allowed_end.isoformat()
        })

    @staticmethod
    def optimization_window_excluded(
        allowed_start: datetime,
        allowed_end: datetime
    ) -> dict:
        return TimeWarningFactory._validate_warning({
            "type": "optimization_window_excluded",
            "severity": "error",
            "message": "Order time windows are outside the selected optimization time range",
            "allowed_start": allowed_start.isoformat(),
            "allowed_end": allowed_end.isoformat()
        })

    @staticmethod
    def low_slack(slack_minutes: int) -> dict:
        return TimeWarningFactory._validate_warning({
            "type": "low_slack",
            "severity": "warning",
            "message": "Low slack time between stops",
            "slack_minutes": slack_minutes
        })
