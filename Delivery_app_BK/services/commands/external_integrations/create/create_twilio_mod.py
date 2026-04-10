from Delivery_app_BK.errors import ValidationFailed
from ....context import ServiceContext


def create_twilio_mod(ctx: ServiceContext):
    raise ValidationFailed(
        "Twilio creation requires connection validation and is not yet implemented."
    )
