from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.models import db
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.utils import model_requires_team, require_team_id


def get_instances(ctx: ServiceContext, model, ids: list[int | str]):
    if not isinstance(ids, list):
        raise ValidationFailed("Ids must be provided as a list.")

    filtered = []
    seen = set()
    for value in ids:
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise ValidationFailed("Each id must be an integer or string.")
        if value in seen:
            continue
        seen.add(value)
        filtered.append(value)

    if not filtered:
        raise ValidationFailed("No ids provided.")

    query = db.session.query(model).filter(model.id.in_(filtered))
    if model_requires_team(model):
        team_id = require_team_id(ctx)
        query = query.filter(model.team_id == team_id)

    instances = query.all()
    by_id = {instance.id: instance for instance in instances}
    missing = [value for value in filtered if value not in by_id]
    if missing:
        raise NotFound(f"Missing related records for ids: {missing}")

    return [by_id[value] for value in filtered]
