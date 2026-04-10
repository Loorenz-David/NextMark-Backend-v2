"""
Fetch the order data exposed to the public client form.

Security:
- Incoming raw token is hashed (SHA-256) before DB lookup — hash never leaks.
- Returns only a safe subset of fields (no driver, plan, or state data).

Returns: { "reference_number": str, "items": [...], "team_name": str, "expires_at": str }
Raises: TokenInvalidError | TokenExpiredError | TokenAlreadyUsedError
"""

from Delivery_app_BK.services.commands.order.client_form._validate_token import validate_and_get_order


def get_client_form_data(token: str) -> dict:
    order = validate_and_get_order(token)

    # Resolve team name; the Order model has a `team` relationship to Team.
    team = getattr(order, "team", None)
    team_name = team.name if team is not None else str(order.team_id)

    items = [
        {"name": item.name, "quantity": item.quantity}
        for item in (order.items or [])
    ]

    return {
        "reference_number": order.reference_number,
        "team_name": team_name,
        "team_timezone": team.time_zone if team is not None else None,
        "items": items,
        "expires_at": order.client_form_token_expires_at.isoformat(),
    }
