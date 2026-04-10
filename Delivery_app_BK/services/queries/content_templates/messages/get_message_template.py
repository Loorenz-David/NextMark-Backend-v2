from Delivery_app_BK.models import MessageTemplate
from Delivery_app_BK.errors import NotFound

from ....context import ServiceContext
from ...get_instance import get_instance
from .serialize_message_templates import serialize_message_templates


def get_message_template(template_id: int, ctx: ServiceContext):
    found_template = get_instance(
        ctx=ctx,
        model=MessageTemplate,
        value=template_id,
    )

    if not found_template:
        raise NotFound(f"Message template with id: {template_id} does not exist.")

    serialized = serialize_message_templates(
        instances=[found_template],
        ctx=ctx,
    )

    return {
        "message_template": serialized[0] if isinstance(serialized, list) else serialized
    }
