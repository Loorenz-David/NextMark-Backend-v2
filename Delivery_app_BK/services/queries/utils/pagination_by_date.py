import base64
import json
from typing import Dict, Any

from sqlalchemy import and_, or_
from sqlalchemy.orm import Query
from sqlalchemy.orm.attributes import InstrumentedAttribute

from Delivery_app_BK.errors import ValidationFailed
from ...utils import to_datetime
from ...context import ServiceContext


def apply_pagination_by_date( 
        query: Query,
        *,
        date_column: InstrumentedAttribute,
        id_column: InstrumentedAttribute,
        params: Dict[str, Any],
        sort: str = 'date_desc'
):
    """
    Assumes the query is already ordered by:
    - date_column ASC/DESC
    - id_column ASC/DESC
    """
    
    # forward pagination
    after_date = params.get("after_date")
    after_id = params.get("after_id")

    # backwards pagination 
    before_date = params.get("before_date")
    before_id = params.get("before_id")

    if after_date and after_id:
        after_date = to_datetime(after_date)
        after_id = int(after_id)

        if sort == 'date_asc':
            query = query.filter(
                or_(
                    date_column > after_date,
                    and_(
                        date_column == after_date,
                        id_column > after_id
                    )
                )
            )

        else:
            query = query.filter(
                    or_(
                        date_column < after_date,
                        and_(
                            date_column == after_date,
                            id_column < after_id
                        )
                    )
                )

    elif before_date and before_id:
    
        before_date = to_datetime(before_date)
        before_id = int(before_id)

        if sort == "date_asc":
            query = query.filter(
                or_(
                    date_column < before_date,
                    and_(
                        date_column == before_date,
                        id_column < before_id
                    )
                )
            )
        else:
            query = query.filter(
                or_(
                    date_column > before_date,
                    and_(
                        date_column == before_date,
                        id_column > before_id
                    )
                )
            )  

    return query


def encode_opaque_cursor(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def decode_opaque_cursor(token: str | None) -> Dict[str, Any] | None:
    if not token:
        return None

    try:
        raw = base64.urlsafe_b64decode(token.encode("utf-8"))
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # pragma: no cover - defensive guard
        raise ValidationFailed("Invalid pagination cursor.") from exc

    if not isinstance(payload, dict):
        raise ValidationFailed("Invalid pagination cursor.")

    return payload


def apply_opaque_pagination_by_date(
        query: Query,
        *,
        date_column: InstrumentedAttribute,
        id_column: InstrumentedAttribute,
        params: Dict[str, Any],
        sort: str = 'date_desc',
        after_key: str = "after_cursor",
        before_key: str = "before_cursor",
):
    after_cursor = decode_opaque_cursor(params.get(after_key))
    before_cursor = decode_opaque_cursor(params.get(before_key))

    if after_cursor:
        after_date = to_datetime(after_cursor.get("creation_date"))
        after_id = int(after_cursor.get("id"))

        if sort == 'date_asc':
            query = query.filter(
                or_(
                    date_column > after_date,
                    and_(
                        date_column == after_date,
                        id_column > after_id,
                    ),
                )
            )
        else:
            query = query.filter(
                or_(
                    date_column < after_date,
                    and_(
                        date_column == after_date,
                        id_column < after_id,
                    ),
                )
            )

    elif before_cursor:
        before_date = to_datetime(before_cursor.get("creation_date"))
        before_id = int(before_cursor.get("id"))

        if sort == "date_asc":
            query = query.filter(
                or_(
                    date_column < before_date,
                    and_(
                        date_column == before_date,
                        id_column < before_id,
                    ),
                )
            )
        else:
            query = query.filter(
                or_(
                    date_column > before_date,
                    and_(
                        date_column == before_date,
                        id_column > before_id,
                    ),
                )
            )

    return query



def is_pagination_backwards( ctx: ServiceContext ):
    return (
        "before_date" in ctx.query_params and
        "before_id" in ctx.query_params
    )

def build_cursor( 
    instance,
    *,
    date_attr,
    id_attr,
    direction = "after",
):
    date_value = getattr( instance, date_attr )
    return {
        f"{direction}_date": date_value.isoformat() if date_value else None,
        f"{direction}_id": getattr( instance, id_attr ),
    }

def build_pagination( 
        page_instances:list, 
        *,
        has_more, 
        date_attr: str,
        id_attr: str,
        ctx: ServiceContext
):
    """
    Builds paginations metadata for cursor-based pagination.

    Assumes:
    - page_instances are already limited
    - query was ordered correctly
    """

    if not page_instances:
        return {
            "has_more": False,
            "next_cursor":None,
            "prev_cursor":None
        }

    if is_pagination_backwards( ctx ):
        page_instances.reverse()
    
    pagination = {
        "has_more": has_more,
        "next_cursor": build_cursor( 
            instance = page_instances[ -1 ], 
            date_attr = date_attr,
            id_attr = id_attr,
            direction = 'after'
        ),
        "prev_cursor": build_cursor( 
            instance = page_instances[ 0 ], 
            date_attr = date_attr,
            id_attr = id_attr,
            direction = 'before'
        ),
    }

    return pagination


def build_opaque_pagination(
        page_instances: list,
        *,
        has_more: bool,
        date_attr: str,
        id_attr: str,
):
    if not page_instances:
        return {
            "has_more": False,
            "next_cursor": None,
            "prev_cursor": None,
        }

    def _build(instance):
        date_value = getattr(instance, date_attr, None)
        return encode_opaque_cursor({
            "creation_date": date_value.isoformat() if date_value else None,
            "id": getattr(instance, id_attr),
        })

    return {
        "has_more": has_more,
        "next_cursor": _build(page_instances[-1]),
        "prev_cursor": _build(page_instances[0]),
    }
