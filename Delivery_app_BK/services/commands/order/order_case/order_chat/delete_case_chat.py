from Delivery_app_BK.models import db, CaseChat
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.commands.base.delete_instance import delete_instance
from Delivery_app_BK.services.commands.utils import extract_ids


def delete_case_chat(ctx: ServiceContext):
    instances = []
    for target_id in extract_ids(ctx):
        instances.append(delete_instance(ctx, CaseChat, target_id))
    db.session.commit()
    return instances
