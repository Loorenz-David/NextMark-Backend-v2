"""Build the client-form configuration exposed to the public (unauthenticated) form.

Takes a team_id resolved server-side from the submission token — never from a
request parameter. Returns only enabled rows and omits internal bookkeeping
fields (client_id, storage_key, created_by_user_id) that the form has no use for.
"""

from typing import Any, Dict

from Delivery_app_BK.models import ClientFormMedia, ClientFormRule, db
from .find_terms_versions import get_active_terms_version
from .get_client_form_settings import find_settings_for_team
from .serialize_client_form_config import DEFAULT_SETTINGS


def build_public_client_form_config(team_id: int) -> Dict[str, Any]:
    settings = find_settings_for_team(team_id)

    terms_enabled = (
        settings.terms_enabled if settings is not None else DEFAULT_SETTINGS["terms_enabled"]
    )
    require_acceptance = (
        settings.require_acceptance
        if settings is not None
        else DEFAULT_SETTINGS["require_acceptance"]
    )
    show_rules = settings.show_rules if settings is not None else DEFAULT_SETTINGS["show_rules"]
    show_media = settings.show_media if settings is not None else DEFAULT_SETTINGS["show_media"]

    terms = None
    if terms_enabled:
        active_version = get_active_terms_version(team_id)
        if active_version is not None:
            terms = {
                "version_id": active_version.id,
                "version_number": active_version.version_number,
                "content": active_version.content,
            }

    rules = []
    if show_rules:
        rule_rows = (
            db.session.query(ClientFormRule)
            .filter(
                ClientFormRule.team_id == team_id,
                ClientFormRule.enabled.is_(True),
            )
            .order_by(ClientFormRule.position.asc(), ClientFormRule.id.asc())
            .all()
        )
        rules = [
            {
                "id": rule.id,
                "position": rule.position,
                "title": rule.title,
                "body": rule.body,
                "icon": rule.icon,
                "image_url": rule.image_url,
            }
            for rule in rule_rows
        ]

    media_by_placement: Dict[str, list] = {}
    if show_media:
        media_rows = (
            db.session.query(ClientFormMedia)
            .filter(
                ClientFormMedia.team_id == team_id,
                ClientFormMedia.enabled.is_(True),
            )
            .order_by(ClientFormMedia.position.asc(), ClientFormMedia.id.asc())
            .all()
        )
        for media in media_rows:
            media_by_placement.setdefault(media.placement, []).append(
                {
                    "id": media.id,
                    "position": media.position,
                    "url": media.url,
                    "alt_text": media.alt_text,
                    "link_url": media.link_url,
                    "title": media.title,
                    "description": media.description,
                }
            )

    return {
        "terms": terms,
        "require_terms_acceptance": bool(terms_enabled and require_acceptance and terms),
        "rules": rules,
        "media": media_by_placement,
    }
