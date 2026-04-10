from __future__ import annotations

from sqlalchemy import text

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.utils import require_team_id


ORDER_SCALAR_ID_START = 1000


def reserve_order_scalar_ids(
    ctx: ServiceContext,
    batch_size: int,
) -> list[int]:
    if batch_size <= 0:
        return []

    team_id = require_team_id(ctx)
    _ensure_order_scalar_counter_row(team_id)

    start_value = db.session.execute(
        text(
            """
            UPDATE order_scalar_counter
            SET next_value = next_value + :batch_size
            WHERE team_id = :team_id
            RETURNING next_value - :batch_size AS start_value
            """
        ),
        {
            "team_id": team_id,
            "batch_size": batch_size,
        },
    ).scalar_one_or_none()

    if start_value is None:
        raise ValidationFailed("Failed to allocate order scalar ids.")

    first_value = int(start_value)
    return [first_value + offset for offset in range(batch_size)]


def _ensure_order_scalar_counter_row(team_id: int) -> None:
    db.session.execute(
        text(
            """
            INSERT INTO order_scalar_counter (team_id, next_value)
            VALUES (:team_id, :next_value)
            ON CONFLICT(team_id) DO NOTHING
            """
        ),
        {
            "team_id": team_id,
            "next_value": ORDER_SCALAR_ID_START,
        },
    )
