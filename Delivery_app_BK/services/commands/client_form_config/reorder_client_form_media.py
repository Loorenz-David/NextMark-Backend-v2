"""Reassign media positions within a single placement.

Media positions are unique per (team, placement), so a reorder is scoped to one
placement and uses the same park-then-write two-pass rewrite as the rule reorder.
"""

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import ClientFormMedia, db
from Delivery_app_BK.services.domain.client_form.media_placement import (
    ALLOWED_MEDIA_PLACEMENTS,
)
from Delivery_app_BK.services.domain.client_form.ordering import normalize_positions
from Delivery_app_BK.services.utils import require_team_id
from ...context import ServiceContext


def reorder_client_form_media(ctx: ServiceContext):
    team_id = require_team_id(ctx)
    incoming = ctx.incoming_data or {}

    placement = incoming.get("placement")
    if placement not in ALLOWED_MEDIA_PLACEMENTS:
        raise ValidationFailed(
            f"Invalid placement '{placement}'. "
            f"Allowed values: {sorted(ALLOWED_MEDIA_PLACEMENTS)}"
        )

    ordered = normalize_positions(incoming.get("ordered_ids"))

    media = (
        db.session.query(ClientFormMedia)
        .filter(
            ClientFormMedia.team_id == team_id,
            ClientFormMedia.placement == placement,
        )
        .all()
    )
    media_by_id = {item.id: item for item in media}

    requested_ids = {entry["target_id"] for entry in ordered}
    if requested_ids != set(media_by_id):
        raise ValidationFailed(
            f"'ordered_ids' must list every media item in placement '{placement}' exactly once."
        )

    parking_offset = max((item.position for item in media), default=0) + 1

    for index, entry in enumerate(ordered):
        media_by_id[entry["target_id"]].position = parking_offset + index
    db.session.flush()

    for entry in ordered:
        media_by_id[entry["target_id"]].position = entry["position"]
    db.session.flush()

    db.session.commit()
    return [entry["target_id"] for entry in ordered]
