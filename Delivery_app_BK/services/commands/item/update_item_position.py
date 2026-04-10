from sqlalchemy.orm.exc import NoResultFound

from Delivery_app_BK.errors import NotFound
from Delivery_app_BK.models import db, Item, ItemPosition
from ...context import ServiceContext
from ...queries.get_instance import get_instance


def update_item_position(
    ctx: ServiceContext,
    item_id: int | str,
    position_id: int | str,
):
    try:
        item_instance: Item = get_instance(ctx, Item, item_id)
        position_instance: ItemPosition = get_instance(ctx, ItemPosition, position_id)
    except NoResultFound as exc:
        raise NotFound(str(exc)) from exc

    item_instance.item_position_id = position_instance.id
    db.session.commit()
    return item_instance
