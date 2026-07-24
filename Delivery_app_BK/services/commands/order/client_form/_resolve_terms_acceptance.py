"""Validate the terms version a client-form submission claims to accept.

Security:
- The accepted version is matched against the team's *currently active* version,
  resolved server-side from the order's team. A stale version id, or one
  belonging to another team, is rejected rather than stored.
- Never route this through ALLOWED_CLIENT_FIELDS in submit_client_form: that set
  is copied onto the order unchecked.

Returns: the ClientFormTermsVersion the customer accepted, or None when the team
does not collect acceptance.
Raises: ValidationFailed
"""

from typing import Any, Optional

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import ClientFormTermsVersion
from Delivery_app_BK.services.domain.client_form.terms import requires_acceptance
from Delivery_app_BK.services.queries.client_form_config.find_terms_versions import (
    get_active_terms_version,
)
from Delivery_app_BK.services.queries.client_form_config.get_client_form_settings import (
    find_settings_for_team,
)


def resolve_terms_acceptance(
    team_id: int,
    payload: dict,
) -> Optional[ClientFormTermsVersion]:
    settings = find_settings_for_team(team_id)
    terms_enabled = bool(getattr(settings, "terms_enabled", False))
    active_version = get_active_terms_version(team_id) if terms_enabled else None

    submitted: Any = payload.get("accepted_terms_version_id") if isinstance(payload, dict) else None

    if active_version is None:
        # Nothing published (or terms disabled) — acceptance cannot be recorded.
        if requires_acceptance(settings):
            raise ValidationFailed(
                "Terms acceptance is required but no terms version has been published."
            )
        return None

    if submitted is None:
        if requires_acceptance(settings):
            raise ValidationFailed("You must accept the terms and conditions to submit this form.")
        return None

    if isinstance(submitted, bool) or not isinstance(submitted, int):
        raise ValidationFailed("'accepted_terms_version_id' must be an integer.")

    if submitted != active_version.id:
        raise ValidationFailed(
            "The accepted terms version is no longer current. Reload the form and try again."
        )

    return active_version
