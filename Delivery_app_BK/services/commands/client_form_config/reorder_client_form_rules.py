"""Reassign rule positions from a caller-supplied ordering.

Positions carry a unique constraint per team, so the rewrite runs in two passes:
every row is first parked above the current maximum, then written down to its
final 0..n-1 slot. A single pass would collide as soon as two rows swap.
"""

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import ClientFormRule, db
from Delivery_app_BK.services.domain.client_form.ordering import normalize_positions
from Delivery_app_BK.services.utils import require_team_id
from ...context import ServiceContext


def reorder_client_form_rules(ctx: ServiceContext):
    team_id = require_team_id(ctx)
    incoming = ctx.incoming_data or {}
    ordered = normalize_positions(incoming.get("ordered_ids"))

    rules = (
        db.session.query(ClientFormRule)
        .filter(ClientFormRule.team_id == team_id)
        .all()
    )
    rules_by_id = {rule.id: rule for rule in rules}

    requested_ids = {entry["target_id"] for entry in ordered}
    if requested_ids != set(rules_by_id):
        raise ValidationFailed(
            "'ordered_ids' must list every rule for this team exactly once."
        )

    parking_offset = max((rule.position for rule in rules), default=0) + 1

    for index, entry in enumerate(ordered):
        rules_by_id[entry["target_id"]].position = parking_offset + index
    db.session.flush()

    for entry in ordered:
        rules_by_id[entry["target_id"]].position = entry["position"]
    db.session.flush()

    db.session.commit()
    return [entry["target_id"] for entry in ordered]
