"""List zone versions for the authenticated team."""
from __future__ import annotations

from Delivery_app_BK.models.tables.zones.zone_version import ZoneVersion
from Delivery_app_BK.zones.services.city_key_normalizer import normalize_city_key
from Delivery_app_BK.services.context import ServiceContext


def list_zone_versions(ctx: ServiceContext) -> list[dict]:
    """Return all zone versions for the team, optionally filtered by city_key."""
    q = ZoneVersion.query.filter_by(team_id=ctx.team_id)

    raw_city = ctx.query_params.get("city_key")
    if raw_city:
        q = q.filter_by(city_key=normalize_city_key(raw_city))

    versions = q.order_by(ZoneVersion.city_key, ZoneVersion.version_number).all()
    return [
        {
            "id": v.id,
            "city_key": v.city_key,
            "version_number": v.version_number,
            "is_active": v.is_active,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in versions
    ]
