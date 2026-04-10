from Delivery_app_BK.models import LabelTemplate
from Delivery_app_BK.errors import NotFound

from ....context import ServiceContext
from ...get_instance import get_instance
from .serialize_label_templates import serialize_label_templates


def get_label_template(template_id: int, ctx: ServiceContext):
    found_template = get_instance(
        ctx=ctx,
        model=LabelTemplate,
        value=template_id,
    )

    if not found_template:
        raise NotFound(f"Label template with id: {template_id} does not exist.")

    serialized = serialize_label_templates(
        instances=[found_template],
        ctx=ctx,
    )

    return {
        "label_template": serialized[0] if isinstance(serialized, list) else serialized
    }
