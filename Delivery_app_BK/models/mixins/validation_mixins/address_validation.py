from sqlalchemy.orm import validates
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from Delivery_app_BK.errors import ValidationFailed
from ...schemas.address_schema import ADDRESS_SCHEMA


class AddressJSONValidationMixin:


    @validates(
    "last_location",
    "client_address",
    "location",
    "pickup_location",
    "start_location",
    "end_location",
    "property_location"
    )
    def _validate_address_fields(self, key, value):
        
        if value is None: 
            return value
        
        try:
            validate(instance=value, schema=ADDRESS_SCHEMA)
        except ValidationError as e:
            raise ValidationFailed(
                f"Invalid address in field '{key}': {e.message}"
            )
        return value