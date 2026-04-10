from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.models import db, LabelTemplate
from ...context import ServiceContext
from Delivery_app_BK.services.queries.get_instance import get_instance


def toggle_template_state(ctx: ServiceContext, template_id: int):

    
    instance:LabelTemplate = get_instance(ctx, LabelTemplate, template_id)

    if not instance:
        raise NotFound(f'label template not found with id: {template_id}', )
    
    if 'enable' not in ctx.incoming_data:
        raise ValidationFailed(f'payload must contain key: "enable" with a bool value.', )


    enable = ctx.incoming_data.get('enable')

    instance.enable = enable

    db.session.commit()
    return instance