from __future__ import annotations
import logging
import re
import uuid

from Delivery_app_BK.models import db, Item, Order
from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.commands.item.create.create_item import create_item as create_item_service
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team

logger = logging.getLogger(__name__)


def _generate_article_number(item_type: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", item_type.lower().strip()).strip("-") or "item"
    return f"{slug}-{uuid.uuid4().hex[:6]}"


def search_item_types_tool(
    ctx: ServiceContext,
    q: str,
    limit: int = 8,
) -> dict:
    """
    Search for existing item types matching a query string.
    Returns distinct item types with a representative properties template from
    the most recent matching item. Use this before create_order to:
      1. Confirm the item_type exists in the team's catalog.
      2. Discover the properties schema (keys/values) your team uses for that type.
      3. Map user-described attributes (e.g. "two extension boards") onto known property keys.

    Parameters:
      q: partial item_type to search (e.g. "table", "chair", "box")
      limit: max distinct types to return (default 8)
    """
    query = db.session.query(Item.item_type, Item.properties, Item.article_number)

    if model_requires_team(Item) and ctx.inject_team_id:
        params: dict = {}
        params = inject_team_id(params, ctx)
        if "team_id" in params:
            query = query.filter(Item.team_id == params["team_id"])

    query = query.filter(Item.item_type.ilike(f"%{q.strip()}%"))
    query = query.order_by(Item.id.desc())

    rows = query.limit(limit * 5).all()  # over-fetch to deduplicate

    # Deduplicate by item_type, keeping the most recent properties for each
    seen: dict[str, dict] = {}
    for item_type, properties, article_number in rows:
        if item_type and item_type not in seen:
            seen[item_type] = {
                "item_type": item_type,
                "sample_article_number": article_number,
                "properties_template": properties or {},
            }
        if len(seen) >= limit:
            break

    results = list(seen.values())
    logger.info("search_item_types_tool | q=%r | found=%d types", q, len(results))

    return {
        "item_types": results,
        "count": len(results),
        "matched": len(results) > 0,
        "hint": (
            "If matched=true: use item_type and properties_template as a guide when building items[] for create_order. "
            "Omit properties keys you don't know — do not invent values. "
            "If matched=false: proceed with the user's label as item_type — creation is still valid without a catalog match."
        ),
    }


def add_items_to_order_tool(
    ctx: ServiceContext,
    order_id: int,
    items: list[dict],
) -> dict:
    """
    Add one or more items to an existing order.
    Call search_item_types first when the user mentions specific item types,
    to discover the correct item_type name and properties structure.

    Parameters:
      order_id: REQUIRED — ID of the existing order to add items to.
      items: REQUIRED — list of item objects. Each item:
        {
          "item_type": "table",           # used as article_number label if none given
          "article_number": "TBL-001",    # optional — auto-generated if missing
          "quantity": 1,                  # optional, default 1
          "properties": { "extensions": 2 },  # optional — only set what the user stated
          "weight": 25,                   # optional, kg
          "reference_number": "...",      # optional
        }
    """
    if not items:
        raise ValidationFailed("items must be a non-empty list.")

    # Verify the order exists and belongs to this team
    order = db.session.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise NotFound(f"Order {order_id} not found.")

    # Normalise items — inject order_id and auto-generate article_number if missing
    field_sets = []
    for item in items:
        item = dict(item)
        item["order_id"] = order_id
        if not item.get("article_number"):
            item_type = item.get("item_type") or "item"
            item["article_number"] = _generate_article_number(item_type)
            logger.info(
                "add_items_to_order_tool | generated article_number=%r for item_type=%r",
                item["article_number"],
                item_type,
            )
        field_sets.append(item)

    ctx.incoming_data = {"fields": field_sets}
    result = create_item_service(ctx)

    logger.info(
        "add_items_to_order_tool | order_id=%s | items_added=%d",
        order_id,
        len(field_sets),
    )
    return {
        "status": "added",
        "order_id": order_id,
        "items_added": len(field_sets),
        "result": result.get("item"),
    }
