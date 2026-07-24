from typing import Any, Dict

from sqlalchemy.orm import Query

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import ClientFormMedia, db
from Delivery_app_BK.services.domain.client_form.media_placement import (
    ALLOWED_MEDIA_PLACEMENTS,
)
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team
from ...context import ServiceContext
from ..utils import str_to_bool


def find_client_form_media(
    params: Dict[str, Any],
    ctx: ServiceContext,
    query: Query | None = None,
):
    query = query or db.session.query(ClientFormMedia)

    # Team scoping
    if model_requires_team(ClientFormMedia) and ctx.inject_team_id:
        params = inject_team_id(params, ctx)

    if "team_id" in params:
        query = query.filter(ClientFormMedia.team_id == params.get("team_id"))

    if "client_id" in params:
        query = query.filter(ClientFormMedia.client_id == params.get("client_id"))

    if "placement" in params:
        placement = params.get("placement")
        if placement not in ALLOWED_MEDIA_PLACEMENTS:
            raise ValidationFailed(
                f"Invalid placement '{placement}'. "
                f"Allowed values: {sorted(ALLOWED_MEDIA_PLACEMENTS)}"
            )
        query = query.filter(ClientFormMedia.placement == placement)

    if "enabled" in params:
        query = query.filter(ClientFormMedia.enabled.is_(str_to_bool(params.get("enabled"))))

    return query.order_by(
        ClientFormMedia.placement.asc(),
        ClientFormMedia.position.asc(),
        ClientFormMedia.id.asc(),
    )
