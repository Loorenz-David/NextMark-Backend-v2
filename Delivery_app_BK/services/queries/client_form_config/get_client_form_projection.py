"""Serve the public client-form projection to an authenticated team device.

The in-store linked device renders the same form as the public token link, so it
needs the same configuration — terms, rules and media — but has no token to fetch
it with. It is authenticated instead, and the team comes from its own claims.

This deliberately reuses `build_public_client_form_config` rather than assembling
an equivalent shape: two surfaces showing the same form must not be able to
disagree about what that form contains, and a second builder is how they would
start to. The team id still comes from the session, never from a parameter.
"""

from typing import Any, Dict

from Delivery_app_BK.services.utils import require_team_id
from ...context import ServiceContext
from .build_public_client_form_config import build_public_client_form_config


def get_client_form_projection(ctx: ServiceContext) -> Dict[str, Any]:
    team_id = require_team_id(ctx)

    return {"client_form_config": build_public_client_form_config(team_id)}
