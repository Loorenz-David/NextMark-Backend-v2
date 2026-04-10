from Delivery_app_BK.models import db, EmailSMTP, Team
from ....context import ServiceContext
from ...base.update_instance import update_instance
from ...utils import extract_targets


def update_email_smtp(ctx: ServiceContext):
    relationship_map = {
        "team_id": Team,
        "team": Team,
    }
    ctx.set_relationship_map(relationship_map)
    instances = []
    for target in extract_targets(ctx):
        instance = update_instance(ctx, EmailSMTP, target["fields"], target["target_id"])
        instances.append(instance.id)
    db.session.commit()
    return instances
