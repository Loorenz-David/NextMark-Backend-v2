"""The post-submit redirect handed to the public client form.

The team is always the one the form token belongs to, never a request value,
and the stored URL is validated again on the way out: a row written before a
rule was tightened, or edited outside the app, must not reach a customer's
browser.
"""

import logging
from typing import Optional, TypedDict

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import ClientFormRedirect, db
from Delivery_app_BK.services.domain.client_form.redirect_url import (
    normalize_redirect_url,
    redirect_url_host,
)

logger = logging.getLogger(__name__)


class PublicRedirect(TypedDict):
    url: str
    host: str


def resolve_public_redirect(team_id: int) -> Optional[PublicRedirect]:
    active = (
        db.session.query(ClientFormRedirect)
        .filter(
            ClientFormRedirect.team_id == team_id,
            ClientFormRedirect.is_active.is_(True),
        )
        .one_or_none()
    )
    if active is None:
        return None

    try:
        url = normalize_redirect_url(active.url)
    except ValidationFailed:
        logger.warning(
            "Skipping invalid client form redirect id=%s team_id=%s", active.id, team_id
        )
        return None

    return {"url": url, "host": redirect_url_host(url)}
