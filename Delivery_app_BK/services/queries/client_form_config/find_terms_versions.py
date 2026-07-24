from typing import Any, Dict, Optional

from sqlalchemy.orm import Query

from Delivery_app_BK.models import ClientFormTermsVersion, db
from Delivery_app_BK.services.utils import inject_team_id, model_requires_team
from ...context import ServiceContext
from ..utils import str_to_bool


def find_terms_versions(
    params: Dict[str, Any],
    ctx: ServiceContext,
    query: Query | None = None,
):
    query = query or db.session.query(ClientFormTermsVersion)

    # Team scoping
    if model_requires_team(ClientFormTermsVersion) and ctx.inject_team_id:
        params = inject_team_id(params, ctx)

    if "team_id" in params:
        query = query.filter(ClientFormTermsVersion.team_id == params.get("team_id"))

    if "is_active" in params:
        query = query.filter(
            ClientFormTermsVersion.is_active.is_(str_to_bool(params.get("is_active")))
        )

    return query.order_by(ClientFormTermsVersion.version_number.desc())


def get_active_terms_version(team_id: int) -> Optional[ClientFormTermsVersion]:
    """Return the team's active terms version, or None when nothing is published.

    Takes team_id directly rather than a ServiceContext: the public client form
    resolves the team from the submission token, not from an authenticated identity.
    """
    return (
        db.session.query(ClientFormTermsVersion)
        .filter(
            ClientFormTermsVersion.team_id == team_id,
            ClientFormTermsVersion.is_active.is_(True),
        )
        .one_or_none()
    )
