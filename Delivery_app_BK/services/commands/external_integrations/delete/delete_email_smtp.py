from Delivery_app_BK.models import db, EmailSMTP
from ....context import ServiceContext
from ...base.delete_instance import delete_instance
from ...utils import extract_ids


def delete_email_smtp(ctx: ServiceContext):
    instances = []
    for target_id in extract_ids(ctx):
        instances.append(delete_instance(ctx, EmailSMTP, target_id))
    db.session.commit()
    return instances
