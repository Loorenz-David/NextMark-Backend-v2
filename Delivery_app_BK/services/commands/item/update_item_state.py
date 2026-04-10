from sqlalchemy.orm.exc import NoResultFound

from Delivery_app_BK.errors import NotFound
from Delivery_app_BK.models import db, Item, ItemState
from ...context import ServiceContext
from ...queries.get_instance import get_instance


def update_item_state(
    ctx: ServiceContext,
    item_id: int | str,
    state_id: int | str,
):
    try:
        item_instance: Item = get_instance(ctx, Item, item_id)
        state_instance: ItemState = get_instance(ctx, ItemState, state_id)
    except NoResultFound as exc:
        raise NotFound(str(exc)) from exc

    item_instance.item_state_id = state_instance.id
    db.session.commit()
    return item_instance
