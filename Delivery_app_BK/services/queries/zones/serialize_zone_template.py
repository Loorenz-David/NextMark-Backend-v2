from __future__ import annotations

from Delivery_app_BK.models import ZoneTemplate
from Delivery_app_BK.route_optimization.constants.route_end_strategy import ROUND_TRIP


def serialize_zone_template(template: ZoneTemplate) -> dict:
    return {
        "id": template.id,
        "team_id": template.team_id,
        "zone_id": template.zone_id,
        "name": template.name,
        "version": template.version,
        "is_active": template.is_active,
        "default_facility_id": getattr(template, "default_facility_id", None),
        "max_orders_per_route": getattr(template, "max_orders_per_route", None),
        "max_vehicles": getattr(template, "max_vehicles", None),
        "operating_window_start": getattr(template, "operating_window_start", None),
        "operating_window_end": getattr(template, "operating_window_end", None),
        "eta_tolerance_seconds": getattr(template, "eta_tolerance_seconds", 0),
        "vehicle_capabilities_required": getattr(
            template,
            "vehicle_capabilities_required",
            None,
        ),
        "preferred_vehicle_ids": getattr(template, "preferred_vehicle_ids", None),
        "default_route_end_strategy": getattr(
            template,
            "default_route_end_strategy",
            ROUND_TRIP,
        ),
        "meta": getattr(template, "meta", None),
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
    }
