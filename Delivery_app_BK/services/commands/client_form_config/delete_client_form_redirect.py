from Delivery_app_BK.models import ClientFormRedirect, db
from ...context import ServiceContext
from ..base.delete_instance import delete_instance
from ..utils import extract_ids


def delete_client_form_redirect(ctx: ServiceContext):
    # Deleting the active page simply leaves the team with no redirect.
    instances = []
    for target_id in extract_ids(ctx):
        instances.append(delete_instance(ctx, ClientFormRedirect, target_id))
    db.session.commit()
    return instances
