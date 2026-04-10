"""List zones belonging to a zone version."""
from __future__ import annotations

from Delivery_app_BK.errors import NotFound
from Delivery_app_BK.models.tables.zones.zone import Zone
from Delivery_app_BK.models.tables.zones.zone_template import ZoneTemplate
from Delivery_app_BK.models.tables.zones.zone_version import ZoneVersion
from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.zones.serialize_zone_template import (
    serialize_zone_template,
)


def list_zones_for_version(ctx: ServiceContext) -> list[dict]:
    """Return all zones for a version that belongs to the authenticated team."""
    version_id = ctx.query_params.get("version_id")

    version = ZoneVersion.query.filter_by(id=version_id, team_id=ctx.team_id).first()
    if version is None:
        raise NotFound(f"Zone version {version_id} not found")

    zones = Zone.query.filter_by(zone_version_id=version_id).order_by(Zone.name).all()
    zone_ids = [zone.id for zone in zones]

    templates_by_zone_id: dict[int, dict] = {}
    if zone_ids:
        active_templates = (
            ZoneTemplate.query.filter(
                ZoneTemplate.team_id == ctx.team_id,
                ZoneTemplate.zone_id.in_(zone_ids),
                ZoneTemplate.is_active.is_(True),
            )
            .order_by(ZoneTemplate.version.desc())
            .all()
        )
        for template in active_templates:
            if template.zone_id in templates_by_zone_id:
                continue
            templates_by_zone_id[template.zone_id] = serialize_zone_template(template)

    return [
        {
            "id": z.id,
            "name": z.name,
            "zone_type": z.zone_type,
            "centroid_lat": z.centroid_lat,
            "centroid_lng": z.centroid_lng,
            "geometry": z.geometry,
            "geometry_simplified": z.geometry_simplified,
            "min_lat": z.min_lat,
            "max_lat": z.max_lat,
            "min_lng": z.min_lng,
            "max_lng": z.max_lng,
            "is_active": z.is_active,
            "template": templates_by_zone_id.get(z.id),
            "zone_color": z.zone_color,
            "created_at": z.created_at.isoformat() if z.created_at else None,
        }
        for z in zones
    ]
