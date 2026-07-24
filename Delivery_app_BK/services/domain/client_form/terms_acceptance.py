"""Validate a terms version id asserted by an authenticated order-write path.

The public client form resolves acceptance from its own submission and is
handled by `services/commands/order/client_form/_resolve_terms_acceptance.py`.
This is the counterpart for the in-store linked device, where the customer
accepts at the counter but the order that has to record it is created — or
patched — afterwards by an authenticated staff client.

Security:
- The submitted id is matched against the team's *currently active* version,
  resolved server-side. A stale id, or one belonging to another team, is
  rejected rather than stored: a staff client must not be able to attach an
  arbitrary version to an order and call it consent.
- Absence is never an error here. Whether acceptance was *required* is decided
  by the form the customer used, at the moment they used it; an order write
  arriving without one simply records none.
"""

from typing import Any, Optional

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import ClientFormTermsVersion
from Delivery_app_BK.services.queries.client_form_config.find_terms_versions import (
    get_active_terms_version,
)


def resolve_asserted_terms_version(
    team_id: int,
    submitted: Any,
) -> Optional[ClientFormTermsVersion]:
    """Return the accepted version, or None when the write asserts no acceptance."""
    if submitted is None:
        return None

    # `bool` is an `int` subclass, and `True` must not be read as version 1.
    if isinstance(submitted, bool) or not isinstance(submitted, int):
        raise ValidationFailed("'accepted_terms_version_id' must be an integer.")

    active_version = get_active_terms_version(team_id)
    if active_version is None or submitted != active_version.id:
        raise ValidationFailed(
            "The accepted terms version is no longer current. "
            "Ask the customer to complete the form again."
        )

    return active_version
