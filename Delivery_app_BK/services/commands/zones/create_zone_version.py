"""Create a new (inactive) zone version for a team and city."""
from __future__ import annotations

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db
from Delivery_app_BK.models.tables.zones.zone_version import ZoneVersion
from Delivery_app_BK.zones.services.city_key_normalizer import normalize_city_key
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


def create_zone_version(ctx: ServiceContext) -> dict:
    """Create a new inactive zone version for (team, city_key).

    The version is created with ``is_active=False``.  Call the activate
    endpoint separately once zones have been added.
    """
    raw_city = ctx.incoming_data.get("city_key") or ctx.incoming_data.get("city")
    if not raw_city:
        raise ValidationFailed("city_key is required")

    city_key = normalize_city_key(raw_city)
    team_id = ctx.team_id

    latest = (
        db.session.query(ZoneVersion)
        .filter_by(team_id=team_id, city_key=city_key)
        .order_by(ZoneVersion.version_number.desc())
        .first()
    )
    next_version_number = (latest.version_number + 1) if latest else 1

    version = ZoneVersion(
        team_id=team_id,
        city_key=city_key,
        version_number=next_version_number,
        is_active=False,
    )
    db.session.add(version)
    db.session.commit()
    return _serialize_version(version)
