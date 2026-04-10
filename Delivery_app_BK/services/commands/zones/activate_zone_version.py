"""Activate a zone version, deactivating all others for the same (team, city_key)."""
from __future__ import annotations

from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.models import db
from Delivery_app_BK.models.tables.zones.zone_version import ZoneVersion
from Delivery_app_BK.services.context import ServiceContext


def _serialize_version(v: ZoneVersion) -> dict:
    return {
        "id": v.id,
        "team_id": v.team_id,
        "city_key": v.city_key,
        "version_number": v.version_number,
        "is_active": v.is_active,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


def activate_zone_version(ctx: ServiceContext) -> dict:
    """Activate a zone version, deactivating all others for the same city_key.

    After committing the activation, enqueues a background job to reassign
    orders created within the past 7 days to the newly active version.
    """
    version_id = ctx.incoming_data.get("version_id")
    if not version_id:
        raise ValidationFailed("version_id is required")

    version = db.session.get(ZoneVersion, version_id)
    if version is None or version.team_id != ctx.team_id:
        raise NotFound(f"Zone version {version_id} not found")

    if version.is_active:
        return _serialize_version(version)

    # Deactivate existing active version for this (team, city_key) before
    # activating the new one, to satisfy the partial unique index.
    (
        db.session.query(ZoneVersion)
        .filter(
            ZoneVersion.team_id == ctx.team_id,
            ZoneVersion.city_key == version.city_key,
            ZoneVersion.id != version.id,
            ZoneVersion.is_active.is_(True),
        )
        .update({"is_active": False})
    )

    version.is_active = True
    db.session.commit()

    # Enqueue background reassignment of recent orders for this city
    from Delivery_app_BK.services.infra.jobs.enqueue import enqueue_job
    from Delivery_app_BK.services.infra.jobs.tasks.zones import reassign_orders_for_new_version_job

    enqueue_job(
        queue_key="default",
        fn=reassign_orders_for_new_version_job,
        args=(version.id,),
        description=f"zones:reassign_orders:{version.id}",
    )

    return _serialize_version(version)
