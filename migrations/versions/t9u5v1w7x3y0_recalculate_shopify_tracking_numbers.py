"""Recalculate tracking numbers for existing Shopify orders.

Shopify orders use their cleaned reference number as the tracking number.  A
separate migration is used so existing tracking tokens and public tracking
links are not regenerated.

Revision ID: t9u5v1w7x3y0
Revises: 2ac9630b7928
Create Date: 2026-07-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "t9u5v1w7x3y0"
down_revision = "2ac9630b7928"
branch_labels = None
depends_on = None


def _resolve_tracking_number(
    *,
    order_id: int,
    external_source: str | None,
    reference_number: str | None,
    order_scalar_id: int | None,
) -> str:
    if external_source == "shopify" and reference_number is not None:
        cleaned_reference = str(reference_number).replace("#", "").strip()
        if cleaned_reference:
            return cleaned_reference

    fallback_id = order_scalar_id if order_scalar_id is not None else order_id
    return f"TRK-{fallback_id}"


def _recalculate_shopify_tracking_numbers(bind) -> int:
    rows = bind.execute(
        sa.text(
            'SELECT id, external_source, reference_number, order_scalar_id '
            'FROM "order" WHERE external_source = :external_source'
        ),
        {"external_source": "shopify"},
    ).fetchall()

    for row in rows:
        tracking_number = _resolve_tracking_number(
            order_id=row[0],
            external_source=row[1],
            reference_number=row[2],
            order_scalar_id=row[3],
        )
        bind.execute(
            sa.text(
                'UPDATE "order" SET tracking_number = :tracking_number '
                'WHERE id = :order_id'
            ),
            {"tracking_number": tracking_number, "order_id": row[0]},
        )

    return len(rows)


def upgrade() -> None:
    _recalculate_shopify_tracking_numbers(op.get_bind())


def downgrade() -> None:
    # Previous tracking numbers cannot be reconstructed reliably from the
    # current order data.  Token and link data remain untouched by this
    # migration.
    pass
