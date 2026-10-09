"""Choose which saved page the public form redirects to, or turn redirect off.

Payload: {"target_id": <id>} activates that page; {"target_id": null} leaves
the team with no active redirect.
"""

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import ClientFormRedirect, db
from Delivery_app_BK.services.utils import require_team_id
from ...context import ServiceContext
from ...queries.get_instance import get_instance


def activate_client_form_redirect(ctx: ServiceContext):
    team_id = require_team_id(ctx)
    incoming = ctx.incoming_data or {}

    if "target_id" not in incoming:
        raise ValidationFailed("Missing 'target_id' in request payload.")

    target_id = incoming.get("target_id")
    if target_id is not None and (isinstance(target_id, bool) or not isinstance(target_id, int)):
        raise ValidationFailed("'target_id' must be an integer or null.")

    # Resolve the target before touching the current active row, so an id from
    # another team fails without side effects.
    target = (
        get_instance(ctx=ctx, model=ClientFormRedirect, value=target_id)
        if target_id is not None
        else None
    )

    current_active = (
        db.session.query(ClientFormRedirect)
        .filter(
            ClientFormRedirect.team_id == team_id,
            ClientFormRedirect.is_active.is_(True),
        )
        .one_or_none()
    )

    if current_active is not None and current_active is not target:
        current_active.is_active = False
        # Flush the deactivation first, so the partial unique index (one active
        # per team) is never transiently violated within the transaction.
        db.session.flush()

    if target is not None:
        target.is_active = True

    db.session.commit()

    return {"active_id": target.id if target is not None else None}
