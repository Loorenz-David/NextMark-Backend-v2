from Delivery_app_BK.models import db, Team, Facility
from Delivery_app_BK.services.requests.infrastructure.facility import (
    parse_create_facility_request,
)
from ....context import ServiceContext
from ...base.create_instance import create_instance
from ...utils import extract_fields, build_create_result


def create_facility(ctx: ServiceContext):
    relationship_map = {
        "team_id": Team,
        "team": Team,
    }
    ctx.set_relationship_map(relationship_map)
    instances = []
    for field_set in extract_fields(ctx):
        request = parse_create_facility_request(dict(field_set))
        instance = create_instance(ctx, Facility, request.to_fields_dict())
        instances.append(instance)
    db.session.add_all(instances)
    db.session.flush()
    result = build_create_result(ctx, instances)
    db.session.commit()
    return result
