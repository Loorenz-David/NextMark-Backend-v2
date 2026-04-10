from sqlalchemy.orm import validates
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from Delivery_app_BK.errors import ValidationFailed
from ...schemas.address_schema import ADDRESS_SCHEMA
from ...schemas.phone_number_schema import PHONE_NUMBER_SCHEMA


class JSONValidationMixin:
    __address_fields__: tuple[str, ...] = ()
    __phone_fields__: tuple[str, ...] = ()
    
    @validates("phone_number", "client_primary_phone", "client_secondary_phone")
    def _validate_json_fields(self, key, value):

        
        try:
            validate(instance=value, schema=PHONE_NUMBER_SCHEMA)
        except ValidationError as e:
            raise ValidationFailed(f"Invalid phone number structure: {e.message}")
            
        return value
    
    