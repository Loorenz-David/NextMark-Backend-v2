"""Publish a new terms-and-conditions version for the team.

Terms versions are immutable — publishing never edits an existing row. It
deactivates the current active version and appends a new one, in a single
transaction so the partial unique index (at most one active per team) never
sees two active rows.
"""

from datetime import datetime, timezone

from Delivery_app_BK.models import ClientFormTermsVersion, db
from Delivery_app_BK.services.domain.client_form.terms import (
    next_version_number,
    validate_terms_content,
)
from Delivery_app_BK.services.utils import require_team_id
from ...context import ServiceContext
from ..utils import extract_fields


def publish_terms_version(ctx: ServiceContext):
    team_id = require_team_id(ctx)
    field_sets = extract_fields(ctx)
    fields = field_sets[0] if field_sets else {}

    content = validate_terms_content(fields.get("content"))

    current_active = (
        db.session.query(ClientFormTermsVersion)
        .filter(
            ClientFormTermsVersion.team_id == team_id,
            ClientFormTermsVersion.is_active.is_(True),
        )
        .one_or_none()
    )

    latest_version_number = (
        db.session.query(db.func.max(ClientFormTermsVersion.version_number))
        .filter(ClientFormTermsVersion.team_id == team_id)
        .scalar()
    )

    if current_active is not None:
        current_active.is_active = False
        # Flush the deactivation before inserting, so the partial unique index
        # is never transiently violated within the transaction.
        db.session.flush()

    instance = ClientFormTermsVersion(
        team_id=team_id,
        version_number=next_version_number(latest_version_number),
        content=content,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        created_by_user_id=ctx.user_id,
    )

    db.session.add(instance)
    db.session.flush()

    result = {"id": instance.id, "version_number": instance.version_number}
    db.session.commit()

    return result
