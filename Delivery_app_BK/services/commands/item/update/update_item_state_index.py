from sqlalchemy import func

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db, ItemState
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.get_instance import get_instance
from Delivery_app_BK.services.utils import require_team_id


def update_item_state_index(ctx: ServiceContext, state_id: int, new_index: int) -> None:
    state: ItemState = get_instance(ctx, ItemState, state_id)

    if state.is_system:
        raise ValidationFailed("System item states cannot be reordered.")

    if state.index is None:
        raise ValidationFailed("Item state index is required to reorder.")

    team_id = require_team_id(ctx)
    next_index = int(new_index)
    if next_index < 1:
        raise ValidationFailed("Index must be greater than zero.")

    base_query = db.session.query(ItemState).filter(
        ItemState.team_id == team_id,
        ItemState.is_system.is_(False),
    )

    max_index = base_query.with_entities(func.max(ItemState.index)).scalar() or 0
    if next_index > max_index:
        next_index = max_index

    current_index = int(state.index)
    if next_index == current_index:
        return

    if next_index > current_index:
        affected = (
            base_query.filter(
                ItemState.index > current_index,
                ItemState.index <= next_index,
            )
            .order_by(ItemState.index.asc())
            .all()
        )
        for other in affected:
            other.index = int(other.index) - 1
    else:
        affected = (
            base_query.filter(
                ItemState.index >= next_index,
                ItemState.index < current_index,
            )
            .order_by(ItemState.index.desc())
            .all()
        )
        for other in affected:
            other.index = int(other.index) + 1

    state.index = next_index
    db.session.commit()
