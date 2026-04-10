from __future__ import annotations

from Delivery_app_BK.services.commands.route_plan.create_plan import create_plan

from ..context_builder import build_ctx
from ..registry import Registry


_ALLOWED_PLAN_FIELDS = frozenset(
    {
        "client_id",
        "label",
        "date_strategy",
        "start_date",
        "end_date",
        "order_ids",
        "zone_ids",
        "route_group_defaults",
    }
)


def process(item: dict, identity: dict, registry: Registry) -> int:
    sid: str | None = item.get("_sid")
    zone_sids: list[str] = item.get("_zone_sids", [])

    plan_fields = {key: value for key, value in item.items() if key in _ALLOWED_PLAN_FIELDS}

    ctx = build_ctx(identity, {"fields": [plan_fields]})
    result = create_plan(ctx)

    bundle = result["created"][0]
    plan_id: int = bundle["delivery_plan"]["id"]
    route_groups: list[dict] = bundle.get("route_groups", [])

    if sid and route_groups:
        registry.register(f"{sid}.rg.default", route_groups[0]["id"])
        for index, zone_sid in enumerate(zone_sids, start=1):
            if index < len(route_groups):
                registry.register(f"{sid}.rg.{zone_sid}", route_groups[index]["id"])

    return plan_id


__all__ = ["process"]
