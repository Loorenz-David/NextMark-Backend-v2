from Delivery_app_BK.models import db, CaseChat, OrderCase, Team
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.commands.base.update_instance import update_instance
from Delivery_app_BK.services.commands.utils import extract_targets


def update_case_chat(ctx: ServiceContext):
    relationship_map = {
        "team_id": Team,
        "order_case_id": OrderCase,
        "order_case": OrderCase,
    }
    ctx.set_relationship_map(relationship_map)
    instances = []
    for target in extract_targets(ctx):
        instance = update_instance(
            ctx, CaseChat, target["fields"], target["target_id"]
        )
        instances.append(instance.id)
    db.session.commit()
    return instances
