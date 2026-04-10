from Delivery_app_BK.models import db, Facility, Team
from Delivery_app_BK.services.requests.infrastructure.facility import (
    parse_update_facility_request,
)
from ....context import ServiceContext
from ...base.update_instance import update_instance
from ...utils import extract_targets


def update_facility(ctx: ServiceContext):
    relationship_map = {
        "team_id": Team,
        "team": Team,
    }
    ctx.set_relationship_map(relationship_map)
    instances = []
    for target in extract_targets(ctx):
        request = parse_update_facility_request(target["fields"])
        instance = update_instance(ctx, Facility, request.to_fields_dict(), target["target_id"])
        instances.append(instance.id)
    db.session.commit()
    return instances
