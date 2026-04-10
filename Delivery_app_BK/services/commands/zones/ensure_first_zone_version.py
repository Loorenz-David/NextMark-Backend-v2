"""Ensure an initial zone version exists for a team and city.

If a version already exists for (team, city_key), returns the latest version.
Otherwise creates version 1 and returns it.
"""
from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.models import Team, db
from Delivery_app_BK.models.tables.zones.zone_version import ZoneVersion
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.zones.services.city_key_normalizer import normalize_city_key


def _serialize_version(v: ZoneVersion) -> dict:
    return {
        "id": v.id,
        "team_id": v.team_id,
        "city_key": v.city_key,
        "version_number": v.version_number,
        "is_active": v.is_active,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


def ensure_first_zone_version(ctx: ServiceContext) -> dict:
    raw_city = ctx.incoming_data.get("city_key") or ctx.incoming_data.get("city")
    if not raw_city:
        raise ValidationFailed("city_key is required")

    city_key = normalize_city_key(raw_city)
    team_id = ctx.team_id
    if not team_id:
        raise ValidationFailed("team_id is required")

    team = db.session.get(Team, team_id)
    if team is None:
        raise NotFound(f"Team {team_id} not found")

    latest = (
        db.session.query(ZoneVersion)
        .filter_by(team_id=team_id, city_key=city_key)
        .order_by(ZoneVersion.version_number.desc())
        .first()
    )
    if latest is not None:
        return _serialize_version(latest)

    version = ZoneVersion(
        team_id=team_id,
        city_key=city_key,
        version_number=1,
        is_active=False,
    )
    db.session.add(version)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ValidationFailed(
            "Unable to create first zone version for this team."
        )
    return _serialize_version(version)
