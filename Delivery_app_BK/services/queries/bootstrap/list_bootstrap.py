from ...context import ServiceContext
from ..item_state.list_item_states import list_item_states
from ..order_states.list_order_states import list_order_states
from ..route_plan.plan_states.list_plan_states import list_plan_states
from ..team_members.list_team_members import list_team_members
from ..content_templates.label.list_label_templates import list_label_templates_bootstrap
from ..content_templates.messages.list_message_templates import list_message_templates_bootstrap
from ..infrastructure.vehicle.list_vehicles import list_vehicles
from ..zones.list_zone_versions import list_zone_versions
from ..zones.list_zones_for_version import list_zones_for_version
from Delivery_app_BK.zones.services.city_key_normalizer import normalize_city_key


def _resolve_bootstrap_city_key(ctx: ServiceContext) -> str | None:
    query_city = (ctx.query_params or {}).get("city_key")
    if query_city:
        return normalize_city_key(query_city)

    if ctx.default_city_key:
        return normalize_city_key(ctx.default_city_key)

    return None


def _build_zones_context(ctx: ServiceContext, city_key: str | None) -> dict:
    if not city_key:
        ctx.set_warning(
            "No city context available for zones bootstrap. Provide city_key or set team default city."
        )
        return {
            "city_key": None,
            "selected_version": None,
            "zones": [],
        }

    original_query_params = ctx.query_params
    try:
        ctx.query_params = {"city_key": city_key}
        versions = list_zone_versions(ctx)

        if not versions:
            return {
                "city_key": city_key,
                "selected_version": None,
                "zones": [],
            }

        selected_version = next((v for v in versions if v.get("is_active")), versions[-1])
        selected_version_id = selected_version["id"]

        ctx.query_params = {"version_id": selected_version_id}
        zones = list_zones_for_version(ctx)

        serialized_zones = []
        for zone in zones:
            template = zone.get("template")
            geometry = zone.get("geometry_simplified") or zone.get("geometry")

            serialized_zones.append(
                {
                    "id": zone.get("id"),
                    "name": zone.get("name"),
                    "zone_type": zone.get("zone_type"),
                    "centroid": {
                        "lat": zone.get("centroid_lat"),
                        "lng": zone.get("centroid_lng"),
                    }
                    if zone.get("centroid_lat") is not None and zone.get("centroid_lng") is not None
                    else None,
                    "bbox": {
                        "min_lat": zone.get("min_lat"),
                        "max_lat": zone.get("max_lat"),
                        "min_lng": zone.get("min_lng"),
                        "max_lng": zone.get("max_lng"),
                    }
                    if all(
                        zone.get(key) is not None
                        for key in ("min_lat", "max_lat", "min_lng", "max_lng")
                    )
                    else None,
                    "geometry_simplified": geometry,
                    "is_active": zone.get("is_active"),
                    "template_ref": {
                        "id": template.get("id"),
                        "name": template.get("name"),
                        "version": template.get("version"),
                    }
                    if template
                    else None,
                    "has_geometry": geometry is not None,
                    "geometry_resolution": "simplified" if geometry is not None else "none",
                }
            )

        return {
            "city_key": city_key,
            "selected_version": {
                "id": selected_version.get("id"),
                "version_number": selected_version.get("version_number"),
                "is_active": selected_version.get("is_active"),
            },
            "zones": serialized_zones,
        }
    finally:
        ctx.query_params = original_query_params

def list_bootstrap(ctx: ServiceContext):
    city_key = _resolve_bootstrap_city_key(ctx)

    ctx.query_params = {}
    payload = {}
    payload["team_members"] = list_team_members(ctx)["team_members"]
    payload["item_states"] = list_item_states(ctx)["item_states"]
    
    payload["order_states"] = list_order_states(ctx)["order_states"]
    payload["plan_states"] = list_plan_states(ctx)["plan_states"]
    payload['label_templates'] = list_label_templates_bootstrap(ctx)['label_templates']

    ctx.query_params = {}
    payload["vehicles"] = list_vehicles(ctx)["vehicles"]
    
    ctx.query_params = {"channel":'email'}
    payload['message_templates_email'] = list_message_templates_bootstrap(ctx)['message_templates']
    ctx.query_params = {"channel":'sms'}
    payload['message_templates_sms'] = list_message_templates_bootstrap(ctx)['message_templates']
    payload["zones_context"] = _build_zones_context(ctx, city_key)
    

    return payload
