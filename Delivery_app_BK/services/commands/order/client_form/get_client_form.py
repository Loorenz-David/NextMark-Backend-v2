"""
Fetch the order data exposed to the public client form.

Security:
- Incoming raw token is hashed (SHA-256) before DB lookup — hash never leaks.
- Returns only a safe subset of fields (no driver or state data). Plan exposure is
  limited to the route plan schedule date rendered in the form header.

Returns: { "reference_number": str, "external_source": str, "items": [...], "team_name": str,
           "expires_at": str, "route_plan_schedule": {...} | None, "config": {...} }
Raises: TokenInvalidError | TokenExpiredError | TokenAlreadyUsedError
         (the latter carries the team's public redirect in `extra`)
"""

from Delivery_app_BK.errors import TokenAlreadyUsedError

from Delivery_app_BK.services.commands.order.client_form._validate_token import validate_and_get_order
from Delivery_app_BK.services.queries.client_form_config.build_public_client_form_config import (
    build_public_client_form_config,
)
from Delivery_app_BK.services.queries.client_form_config.resolve_public_redirect import (
    resolve_public_redirect,
)


def get_client_form_data(token: str) -> dict:
    try:
        order = validate_and_get_order(token)
    except TokenAlreadyUsedError as e:
        # A customer reopening a spent link is offered the team's page again.
        e.extra = {"redirect": resolve_public_redirect(e.team_id) if e.team_id is not None else None}
        raise

    # Resolve team name; the Order model has a `team` relationship to Team.
    team = getattr(order, "team", None)
    team_name = team.name if team is not None else str(order.team_id)

    items = [
        {"item_type": item.item_type, "quantity": item.quantity}
        for item in (order.items or [])
    ]

    # Route plan schedule date for the form header. Nullable on three fronts:
    # the order may be unassigned (no plan), and an assigned plan may have null
    # start/end dates. Shape mirrors serialize_plans so nothing new is invented.
    plan = order.route_plan
    route_plan_schedule = (
        {
            "date_strategy": plan.date_strategy,
            "start_date": plan.start_date.isoformat() if plan.start_date else None,
            "end_date": plan.end_date.isoformat() if plan.end_date else None,
        }
        if plan is not None
        else None
    )

    return {
        "order_scalar_id": order.order_scalar_id,
        "reference_number": order.reference_number,
        "external_source": order.external_source,
        "team_timezone": team.time_zone if team is not None else None,
        "items": items,
        "expires_at": order.client_form_token_expires_at.isoformat(),
        "route_plan_schedule": route_plan_schedule,
        # Team is resolved from the token, never from a request parameter.
        "config": build_public_client_form_config(order.team_id),
    }
