from Delivery_app_BK.models import db, Team, LabelTemplate
from ...context import ServiceContext
from ..base.create_instance import create_instance
from ..utils import extract_fields, build_create_result


def create_label_template(ctx: ServiceContext):
    relationship_map = {
        "team_id": Team,
        "team": Team,
    }
    ctx.set_relationship_map(relationship_map)
    instances = []

    for field_set in extract_fields(ctx):
       
        instance = create_instance(ctx, LabelTemplate, dict(field_set))
        instances.append(instance)

    db.session.add_all(instances)
    db.session.flush()
    result = build_create_result(ctx, instances)
    db.session.commit()
    return result
