from Delivery_app_BK.models import Zone


def serialize_zone(zone: Zone) -> dict:
    return {
        "id": zone.id,
        "team_id": zone.team_id,
        "zone_version_id": zone.zone_version_id,
        "city_key": zone.city_key,
        "name": zone.name,
        "zone_color": zone.zone_color,
        "zone_type": zone.zone_type,
        "centroid_lat": zone.centroid_lat,
        "centroid_lng": zone.centroid_lng,
        "geometry": zone.geometry,
        "min_lat": zone.min_lat,
        "max_lat": zone.max_lat,
        "min_lng": zone.min_lng,
        "max_lng": zone.max_lng,
        "is_active": zone.is_active,
        "created_at": zone.created_at.isoformat() if zone.created_at else None,
        "template": None,
    }
