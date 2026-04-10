from sqlalchemy.orm import validates
from jsonschema import validate
from jsonschema.exceptions import ValidationError

from Delivery_app_BK.errors import ValidationFailed
from ...schemas.service_time_schema import SERVICE_TIME_SCHEMA


class ServiceTimeJSONValidationMixin:
    @validates("service_time", "stops_service_time")
    def _validate_service_time_fields(self, key, value):
        if value is None:
            return value

        try:
            validate(instance=value, schema=SERVICE_TIME_SCHEMA)
        except ValidationError as e:
            raise ValidationFailed(
                f"Invalid service time in field '{key}': {e.message}"
            )
        return value
