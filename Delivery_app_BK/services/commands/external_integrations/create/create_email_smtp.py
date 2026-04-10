from Delivery_app_BK.errors import ValidationFailed
from ....context import ServiceContext


def create_email_smtp(ctx: ServiceContext):
    raise ValidationFailed(
        "Email SMTP creation requires connection validation and is not yet implemented."
    )
