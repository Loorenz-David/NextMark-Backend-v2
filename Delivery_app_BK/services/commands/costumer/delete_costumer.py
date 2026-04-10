from __future__ import annotations

from sqlalchemy.exc import InvalidRequestError

from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.models import Costumer, Order, Team, db
from Delivery_app_BK.services.utils import model_requires_team, require_team_id

from ...context import ServiceContext
from ..utils import extract_ids


def delete_costumer(ctx: ServiceContext):
    ctx.set_relationship_map({"team_id": Team})
    target_ids = extract_ids(ctx)
    int_target_ids = _validate_int_targets(target_ids)
    team_id = require_team_id(ctx)

    query = db.session.query(Costumer).filter(Costumer.id.in_(int_target_ids))
    if model_requires_team(Costumer) and ctx.check_team_id:
        query = query.filter(Costumer.team_id == team_id)
    instances = query.all()
    by_id = {instance.id: instance for instance in instances}

    missing = [target_id for target_id in int_target_ids if target_id not in by_id]
    if missing:
        raise NotFound(f"Costumers not found: {missing}")

    ordered_instances = [by_id[target_id] for target_id in int_target_ids]

    def _apply() -> None:
        for instance in ordered_instances:
            has_orders = (
                db.session.query(Order.id)
                .filter(Order.costumer_id == instance.id)
                .limit(1)
                .scalar()
            )
            if has_orders:
                raise ValidationFailed("Cannot delete costumer with linked orders")
            db.session.delete(instance)

    try:
        with db.session.begin():
            _apply()
    except InvalidRequestError as exc:
        if "already begun" not in str(exc).lower():
            raise
        _apply()
        db.session.commit()

    return {"deleted": {"costumer_ids": int_target_ids}}


def _validate_int_targets(target_ids: list[int | str]) -> list[int]:
    parsed: list[int] = []
    for target_id in target_ids:
        if not isinstance(target_id, int):
            raise ValidationFailed("Costumer delete target_ids must be integers")
        parsed.append(target_id)
    return parsed

