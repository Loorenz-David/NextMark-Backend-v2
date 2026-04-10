from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, literal, select, text, union_all
from sqlalchemy.exc import DBAPIError

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import Order, db
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.order.find_orders import find_orders
from Delivery_app_BK.services.requests.order.update_orders_route_plan_batch import (
    OrderBatchSelectionRequest,
)
from Delivery_app_BK.services.utils import model_requires_team, require_team_id


logger = logging.getLogger(__name__)

SELECTION_RESOLVER_TIMEOUT_MS = 2000
MAX_RESOLVED_COUNT = 50000
SAMPLE_IDS_LIMIT = 50
LARGE_SELECTION_LOG_THRESHOLD = 10000
SELECTION_TIMEOUT_MESSAGE = "Selection resolution timed out. Please refine your filters."
SELECTION_TOO_LARGE_MESSAGE = "Selection too large. Please refine your filters."


@dataclass(frozen=True)
class ResolvedOrderBatchSelection:
    signature: str
    resolved_count: int
    sample_ids: list[int]
    order_ids: list[int]


def resolve_order_batch_selection(
    ctx: ServiceContext,
    selection: OrderBatchSelectionRequest,
    *,
    endpoint: str,
    include_order_ids: bool,
) -> ResolvedOrderBatchSelection:
    try:
        _set_local_statement_timeout()
        resolved_query = _build_resolved_order_ids_query(ctx, selection)

        if include_order_ids:
            resolved_ids = _fetch_ids(resolved_query)
            resolved_count = len(resolved_ids)
            _ensure_max_resolved_count(resolved_count)
            sample_ids = resolved_ids[:SAMPLE_IDS_LIMIT]
        else:
            resolved_count = _count_ids(resolved_query)
            _ensure_max_resolved_count(resolved_count)
            sample_ids = _fetch_ids(resolved_query.limit(SAMPLE_IDS_LIMIT))
            resolved_ids = []
    except DBAPIError as exc:
        if _is_statement_timeout_error(exc):
            logger.info(
                "Selection resolver timeout | endpoint=%s team_id=%s signature=%s",
                endpoint,
                ctx.team_id,
                selection.signature,
            )
            raise ValidationFailed(SELECTION_TIMEOUT_MESSAGE) from exc
        raise

    _log_large_selection(
        ctx=ctx,
        endpoint=endpoint,
        selection=selection,
        resolved_count=resolved_count,
    )

    return ResolvedOrderBatchSelection(
        signature=selection.signature,
        resolved_count=resolved_count,
        sample_ids=sample_ids,
        order_ids=resolved_ids,
    )


def _build_resolved_order_ids_query(
    ctx: ServiceContext,
    selection: OrderBatchSelectionRequest,
):
    candidate_ids_subquery = _build_candidate_ids_subquery(ctx, selection)
    query = (
        db.session.query(Order.id.label("id"))
        .join(candidate_ids_subquery, candidate_ids_subquery.c.id == Order.id)
    )

    if model_requires_team(Order) and ctx.check_team_id:
        query = query.filter(Order.team_id == require_team_id(ctx))

    if selection.excluded_order_ids:
        query = query.filter(~Order.id.in_(selection.excluded_order_ids))

    return query.distinct().order_by(Order.id.asc())


def _build_candidate_ids_subquery(
    ctx: ServiceContext,
    selection: OrderBatchSelectionRequest,
):
    selection_selects = []

    snapshot_selects = _build_snapshot_selects(ctx, selection)
    if snapshot_selects:
        snapshot_union = (
            union_all(*snapshot_selects)
            if len(snapshot_selects) > 1
            else snapshot_selects[0]
        )
        snapshot_union_subquery = snapshot_union.subquery("snapshot_union_ids")
        selection_selects.append(select(snapshot_union_subquery.c.id.label("id")))

    manual_selects = _build_manual_id_selects(selection.manual_order_ids)
    if manual_selects:
        manual_union = (
            union_all(*manual_selects)
            if len(manual_selects) > 1
            else manual_selects[0]
        )
        manual_union_subquery = manual_union.subquery("manual_union_ids")
        selection_selects.append(select(manual_union_subquery.c.id.label("id")))

    if not selection_selects:
        return select(literal(-1).label("id")).where(text("1=0")).subquery("empty_candidate_ids")

    combined_union = (
        union_all(*selection_selects)
        if len(selection_selects) > 1
        else selection_selects[0]
    )
    combined_subquery = combined_union.subquery("selection_union_ids")
    return select(combined_subquery.c.id.label("id")).distinct().subquery("selection_candidate_ids")


def _build_snapshot_selects(
    ctx: ServiceContext,
    selection: OrderBatchSelectionRequest,
) -> list[Any]:
    snapshot_selects: list[Any] = []
    for snapshot in selection.select_all_snapshots:
        params = dict(snapshot.query)
        snapshot_query = find_orders(
            params=params,
            ctx=ctx,
            query=db.session.query(Order.id.label("id")),
        )
        snapshot_query = (
            snapshot_query
            .with_entities(Order.id.label("id"))
            .order_by(None)
            .limit(None)
            .offset(None)
        )
        snapshot_selects.append(snapshot_query.statement)

    return snapshot_selects


def _build_manual_id_selects(manual_order_ids: list[int]) -> list[Any]:
    return [select(literal(order_id).label("id")) for order_id in manual_order_ids]


def _set_local_statement_timeout() -> None:
    bind = db.session.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return
    db.session.execute(text(f"SET LOCAL statement_timeout = {int(SELECTION_RESOLVER_TIMEOUT_MS)}"))


def _count_ids(query) -> int:
    count_subquery = query.subquery("resolved_selection_count")
    return int(
        db.session.query(func.count())
        .select_from(count_subquery)
        .scalar()
        or 0
    )


def _fetch_ids(query) -> list[int]:
    rows = query.all()
    ids: list[int] = []
    for row in rows:
        if isinstance(row, tuple):
            value = row[0]
        else:
            value = getattr(row, "id", None)
        if type(value) is int and value > 0:
            ids.append(value)
    return ids


def _ensure_max_resolved_count(resolved_count: int) -> None:
    if resolved_count > MAX_RESOLVED_COUNT:
        raise ValidationFailed(SELECTION_TOO_LARGE_MESSAGE)


def _is_statement_timeout_error(exc: DBAPIError) -> bool:
    original = getattr(exc, "orig", None)
    pg_code = getattr(original, "pgcode", None)
    if pg_code == "57014":
        return True
    return "statement timeout" in str(exc).lower()


def _log_large_selection(
    *,
    ctx: ServiceContext,
    endpoint: str,
    selection: OrderBatchSelectionRequest,
    resolved_count: int,
) -> None:
    if resolved_count < LARGE_SELECTION_LOG_THRESHOLD:
        return

    logger.info(
        "Large batch selection executed | endpoint=%s resolved_count=%s snapshot_count=%s manual_count=%s exclusions_count=%s team_id=%s signature=%s",
        endpoint,
        resolved_count,
        len(selection.select_all_snapshots),
        len(selection.manual_order_ids),
        len(selection.excluded_order_ids),
        ctx.team_id,
        selection.signature,
    )
