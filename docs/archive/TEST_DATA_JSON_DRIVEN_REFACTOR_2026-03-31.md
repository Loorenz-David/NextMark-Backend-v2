# Test Data System — JSON-Driven Refactor

**Status:** Under development
**Scope:** `Back_end/Delivery_app_BK/services/commands/test_data/`
**Related tests:** `Back_end/tests/unit/services/commands/test_data/`

---

## 1. Context and Motivation

The current test data system lives at:
```
Delivery_app_BK/services/commands/test_data/
  __init__.py
  orchestrator.py
  plan_data_creators.py
  zone_data_creators.py
  facility_data_creators.py
  vehicle_data_creators.py
  order_data_creators.py
  item_types_data_creators.py
  item_generator.py
  route_solution_settings_updater.py
  cleanup.py
  config/
    __init__.py
    plan_defaults.py
    zone_defaults.py
    facility_defaults.py
    vehicle_defaults.py
    order_defaults.py
    item_types_defaults.py
    item_generation_defaults.py
    route_solution_update_defaults.py
```

The problem: data shape is hardcoded into functions. To change what gets created, you modify function parameters or config constants. This makes tests brittle and the system hard to extend.

The goal: replace the whole system with a single entry point `create_test_data(identity, payload)` where `payload` is a plain JSON object describing exactly what to create. All customisation happens in the JSON, not in function arguments.

---

## 2. What Gets Deleted

Delete all of the following files completely:

```
test_data/config/__init__.py
test_data/config/plan_defaults.py
test_data/config/zone_defaults.py
test_data/config/facility_defaults.py
test_data/config/vehicle_defaults.py
test_data/config/order_defaults.py
test_data/config/item_types_defaults.py
test_data/config/item_generation_defaults.py
test_data/config/route_solution_update_defaults.py
test_data/orchestrator.py
test_data/plan_data_creators.py
test_data/zone_data_creators.py
test_data/facility_data_creators.py
test_data/vehicle_data_creators.py
test_data/order_data_creators.py
test_data/item_types_data_creators.py
test_data/item_generator.py
test_data/route_solution_settings_updater.py
```

Also delete all existing unit tests under:
```
tests/unit/services/commands/test_data/
```

The `cleanup.py` file is kept but modified (see Section 11).

---

## 3. New File Tree

```
test_data/
  __init__.py              ← Public API only
  creator.py               ← Dispatch loop
  registry.py              ← Registry class
  ref_map.py               ← Declarative $key → fk_column mapping
  resolver.py              ← resolve_item() pure function
  context_builder.py       ← build_ctx() helper
  cleanup.py               ← Modified (see Section 11)
  processors/
    __init__.py
    item_property.py       ← NEW: ItemProperty catalog record
    item_type.py           ← NEW: ItemType catalog record (links to ItemProperty via M:N)
    facility.py
    vehicle.py
    zone_version.py
    zone.py
    zone_template.py
    route_plan.py
    order.py
    order_delivery_window.py
    order_zone_assignment.py

tests/unit/services/commands/test_data/
  test_registry.py
  test_resolver.py
  test_creator.py
  processors/
    test_item_property.py
    test_item_type.py
    test_facility.py
    test_vehicle.py
    test_zone_version.py
    test_zone.py
    test_zone_template.py
    test_route_plan.py
    test_order.py
    test_order_delivery_window.py
    test_order_zone_assignment.py
```

---

## 4. Payload Format

The caller passes two arguments:

```python
create_test_data(identity: dict, payload: dict) -> dict
```

- `identity` — the same identity dict currently passed to `ServiceContext`. Must contain `team_id` (or `active_team_id`) and `user_id` at minimum.
- `payload` — flat dict with entity keys at the top level.

### Full payload example

```json
{
  "item_property": [
    { "$id": "ip_condition", "name": "test-Condition", "field_type": "select",
      "options": ["New", "Used", "Damaged"], "required": false },
    { "$id": "ip_color", "name": "test-Color", "field_type": "text", "required": false },
    { "$id": "ip_fragile", "name": "test-Fragile", "field_type": "check_box", "required": false }
  ],
  "item_type": [
    { "$id": "it_chair", "name": "test-Vintage Chair",
      "$properties": ["ip_condition", "ip_color", "ip_fragile"] },
    { "$id": "it_table", "name": "test-Table",
      "$properties": ["ip_condition", "ip_color"] }
  ],
  "facility": [
    { "$id": "f1", "name": "Kista Depot", "facility_type": "warehouse",
      "can_dispatch": true,
      "property_location": {"lat": 59.403, "lng": 17.927, "address": "Kista, Stockholm"} }
  ],
  "vehicle": [
    { "$id": "v1", "$facility": "f1", "label": "Van 1", "registration_number": "ABC-001" },
    { "$id": "v2", "$facility": "f1", "label": "Van 2", "registration_number": "ABC-002" }
  ],
  "zone_version": [
    { "$id": "zv1", "city_key": "stockholm" }
  ],
  "zone": [
    { "$id": "z1", "$zone_version": "zv1", "name": "North Zone", "zone_type": "user" },
    { "$id": "z2", "$zone_version": "zv1", "name": "South Zone", "zone_type": "user" }
  ],
  "zone_template": [
    { "$zone": "z1", "$facility": "f1", "name": "North Zone Template",
      "default_route_end_strategy": "round_trip" },
    { "$zone": "z2", "$facility": "f1", "name": "South Zone Template",
      "default_route_end_strategy": "round_trip" }
  ],
  "route_plan": [
    { "$id": "p1", "$zones": ["z1", "z2"], "label": "Monday Plan",
      "start_date": "2026-04-01T00:00:00Z", "end_date": "2026-04-01T23:59:59Z" }
  ],
  "order": [
    { "$id": "o1", "$route_plan": "p1", "$route_group": "p1.rg.z1",
      "reference_number": "test-001", "client_first_name": "Erik",
      "client_last_name": "Svensson",
      "client_address": {"lat": 59.41, "lng": 17.93, "address": "Kista 1, Stockholm"},
      "operation_type": "dropoff", "order_plan_objective": "local_delivery",
      "items": [
        { "article_number": "CHAIR-001", "item_type": "test-Vintage Chair",
          "quantity": 2, "weight": 12000, "dimension_depth": 55, "dimension_height": 100, "dimension_width": 50,
          "properties": [
            {"name": "test-Condition", "value": "Used"},
            {"name": "test-Color", "value": "Oak Brown"}
          ]
        }
      ],
      "delivery_windows": [
        { "start_at": "2026-04-01T09:00:00Z", "end_at": "2026-04-01T17:00:00Z",
          "window_type": "preferred" }
      ]
    },
    { "$id": "o2", "$route_plan": "p1", "$route_group": "p1.rg.default",
      "reference_number": "test-002", "client_first_name": "Sara",
      "client_last_name": "Larsson",
      "client_address": {"lat": 59.39, "lng": 17.91, "address": "Solna 5, Stockholm"},
      "operation_type": "dropoff", "order_plan_objective": "local_delivery" }
  ]
}
```

### Key rules

- `$id` — a symbolic local alias for this instance. Used by other items to reference it. **Never sent to the DB or any service.** Must be unique within the payload.
- `$<key>` — a reference to another entity's `$id`. Resolved to a DB integer ID before the processor runs.
- `$zones` on `route_plan` is a **list ref**: `["z1", "z2"]`. Each element is resolved individually.
- `$properties` on `item_type` is also a **list ref**: `["ip_condition", "ip_color"]`. Each element resolved to an `ItemProperty` DB ID.
- All other `$<key>` refs are **scalar refs**: a single string `"f1"`.
- Entity keys must appear in the payload in topological order (see Section 9 for processing order). But the dispatcher enforces a fixed topological order regardless of key order in the JSON.
- Any entity key not present in the payload is simply skipped.

### Critical: `Item.item_type` is a string, not a foreign key

The `Item` model (order line item) has `item_type = Column(String)` — a plain text column storing the type name. It does **not** have a FK to the `ItemType` table. Similarly, `Item.properties` is a `JSONB` column storing a denormalized snapshot of property name/value pairs.

This means:
- When creating order items inline, pass `"item_type": "test-Vintage Chair"` as a string (copy the name from your `item_type` catalog entry).
- `properties` on items are plain dicts: `[{"name": "test-Condition", "value": "Used"}]`. These are snapshots at order time — not FK references.
- There is no `$ref` mechanism for inline order items. They use plain string values.
- The `ItemType` / `ItemProperty` catalog exists so the UI can show users what types and properties are available. The actual storage on `Item` is always denormalized.

### `delivery_windows` inline on orders

Delivery windows can be passed inline in the order payload via the `delivery_windows` array (preferred approach). Each window requires `start_at`, `end_at`, and `window_type`. If you use inline delivery windows, you do **not** need to use the separate `order_delivery_window` entity in the payload.

The `order_delivery_window` entity in the payload is reserved for adding windows to a pre-existing order (post-creation). For new orders, always use inline `delivery_windows`.

### `route_plan_id` + `route_group_id` must be provided together

The order request parser enforces: if `route_plan_id` is provided then `route_group_id` is also required, and vice versa. You cannot provide one without the other. Either provide both `$route_plan` and `$route_group`, or omit both (creating an unlinked order).

### `route_group` auto-naming convention

When `create_plan` is called with `zone_ids`, it automatically creates:
- One **default no-zone bucket** route_group (`is_system_default_bucket=True`, `zone_id=None`)
- One route_group per zone_id passed

These are auto-registered in the registry by the route_plan processor using stable names:
- `{plan_$id}.rg.default` → the no-zone bucket route_group ID
- `{plan_$id}.rg.{zone_$id}` → zone-specific route_group ID

So if your plan `$id` is `"p1"` and your zone `$id` is `"z1"`, you reference the route_group as `"$route_group": "p1.rg.z1"` in order items.

---

## 5. `registry.py`

The registry tracks created DB IDs, indexed by their symbolic `$id` and by entity key + DB ID for reverse lookups.

```python
# test_data/registry.py
from __future__ import annotations


class RefResolutionError(Exception):
    """Raised when a $ref cannot be resolved to a DB ID."""


class Registry:
    def __init__(self) -> None:
        # forward: sid → db_id
        self._forward: dict[str, int] = {}
        # reverse: entity_key → {db_id → sid}
        self._reverse: dict[str, dict[int, str]] = {}

    def register(self, sid: str, db_id: int, entity_key: str | None = None) -> None:
        """Register a symbolic ID against a DB integer ID.

        entity_key is required to support reverse_lookup.
        """
        if not isinstance(sid, str) or not sid:
            raise ValueError(f"sid must be a non-empty string, got {sid!r}")
        if not isinstance(db_id, int) or db_id <= 0:
            raise ValueError(f"db_id must be a positive integer, got {db_id!r}")
        self._forward[sid] = db_id
        if entity_key:
            self._reverse.setdefault(entity_key, {})[db_id] = sid

    def resolve(self, sid: str) -> int:
        """Resolve a symbolic ID to its DB integer ID.

        Raises RefResolutionError if not found.
        """
        if sid not in self._forward:
            raise RefResolutionError(
                f"Cannot resolve ref ${sid!r}: no entity with that $id has been registered. "
                "Check that the referenced entity appears earlier in the payload and that "
                "its $id matches exactly."
            )
        return self._forward[sid]

    def reverse_lookup(self, entity_key: str, db_id: int) -> str:
        """Look up a symbolic ID by entity key and DB ID.

        Raises RefResolutionError if not found.
        """
        entity_map = self._reverse.get(entity_key, {})
        if db_id not in entity_map:
            raise RefResolutionError(
                f"No $id registered for {entity_key} with DB id={db_id}."
            )
        return entity_map[db_id]

    def is_registered(self, sid: str) -> bool:
        return sid in self._forward


__all__ = ["Registry", "RefResolutionError"]
```

---

## 6. `ref_map.py`

Declarative mapping from `$key` → FK column name (or `(fk_column, "list")` for list refs).

```python
# test_data/ref_map.py
from __future__ import annotations

# REF_FIELD_MAP[entity_key][$key] = fk_column_name | (fk_column_name, "list")
#
# Scalar ref:  "$facility": "home_facility_id"
#   → replaces $facility with the resolved DB ID, sets key "home_facility_id"
#
# List ref:    "$zones": ("zone_ids", "list")
#   → replaces $zones with [resolved_id, ...], sets key "zone_ids"

REF_FIELD_MAP: dict[str, dict[str, str | tuple[str, str]]] = {
    # Item catalog — item_property has no $refs (all fields are plain values)
    "item_type": {
        "$properties": ("properties", "list"),  # list of ItemProperty DB IDs → M:N join
    },
    "vehicle": {
        "$facility": "home_facility_id",
    },
    "zone": {
        "$zone_version": "version_id",
    },
    "zone_template": {
        "$zone": "zone_id",
        "$facility": "default_facility_id",
    },
    "route_plan": {
        "$zones": ("zone_ids", "list"),
    },
    "route_solution": {
        "$route_group": "route_group_id",
        "$vehicle": "vehicle_id",
        "$start_facility": "start_facility_id",
        "$end_facility": "end_facility_id",
    },
    "order": {
        "$route_plan": "route_plan_id",
        "$route_group": "route_group_id",
    },
    "order_delivery_window": {
        "$order": "order_id",
    },
    "order_zone_assignment": {
        "$order": "order_id",
        "$zone": "zone_id",
        "$zone_version": "zone_version_id",
    },
}

__all__ = ["REF_FIELD_MAP"]
```

**Notes:**
- `item_type.$properties` is a list ref — resolves each symbolic property $id to its DB integer ID, then passes the list to `create_item_type` via the `properties` field. The service's `relationship_map` (`"properties": ItemProperty`) handles the M:N join table (`type_property_association`) automatically. **No separate join entity is needed.**
- `zone_template` uses `$zone` → `zone_id` and `$facility` → `default_facility_id`. The `preferred_vehicle_ids` JSONB column accepts raw integer lists directly — no `$ref` needed. Pass them as regular integers or omit entirely.
- `route_plan` has no scalar FK refs — only the list ref `$zones`.
- `order` has both `$route_plan` and `$route_group`. Both are optional: you can create unlinked orders by omitting them. But if one is provided, both must be provided (enforced by the request parser).

---

## 7. `resolver.py`

Pure function. No I/O, no DB. Takes an item dict, strips `$id` and `_meta` keys, resolves all `$key` refs, returns a clean dict safe to pass to a processor.

```python
# test_data/resolver.py
from __future__ import annotations

from .ref_map import REF_FIELD_MAP
from .registry import RefResolutionError, Registry


def resolve_item(entity_key: str, item: dict, registry: Registry) -> dict:
    """Strip $id, resolve all $key refs, return a clean dict for the processor.

    Args:
        entity_key: The payload key this item belongs to (e.g. "facility", "order").
        item: Raw item dict from the payload.
        registry: The live registry of already-created entities.

    Returns:
        Clean dict with all $key refs replaced by their resolved DB integer IDs.

    Raises:
        RefResolutionError: If any $ref cannot be resolved.
    """
    ref_rules = REF_FIELD_MAP.get(entity_key, {})
    output: dict = {}

    for key, value in item.items():
        # Strip symbolic ID — never forwarded to processors
        if key == "$id":
            continue

        # Strip internal metadata keys injected by the dispatch loop
        if key.startswith("_"):
            continue

        # Handle $ref keys
        if key.startswith("$"):
            if key not in ref_rules:
                raise RefResolutionError(
                    f"Unknown $ref key {key!r} on entity {entity_key!r}. "
                    f"Registered $refs for this entity: {sorted(ref_rules)}"
                )
            rule = ref_rules[key]

            if isinstance(rule, tuple):
                # List ref: ("zone_ids", "list")
                fk_column, ref_type = rule
                if ref_type != "list":
                    raise ValueError(f"Unknown ref_type {ref_type!r} in REF_FIELD_MAP")
                if not isinstance(value, list):
                    raise RefResolutionError(
                        f"{key} on {entity_key!r} must be a list of $id strings."
                    )
                output[fk_column] = [
                    _resolve_single(entity_key, key, ref, registry)
                    for ref in value
                ]
            else:
                # Scalar ref: "home_facility_id"
                fk_column = rule
                output[fk_column] = _resolve_single(entity_key, key, value, registry)
        else:
            output[key] = value

    return output


def _resolve_single(entity_key: str, ref_key: str, sid: str, registry: Registry) -> int:
    if not isinstance(sid, str):
        raise RefResolutionError(
            f"{ref_key} on {entity_key!r} must be a string $id, got {type(sid).__name__!r}."
        )
    try:
        return registry.resolve(sid)
    except RefResolutionError:
        raise RefResolutionError(
            f"Cannot resolve {ref_key}={sid!r} on entity {entity_key!r}. "
            "The referenced $id has not been registered yet — check processing order."
        ) from None


__all__ = ["resolve_item"]
```

---

## 8. `context_builder.py`

Minimal helper so processors don't construct `ServiceContext` directly.

```python
# test_data/context_builder.py
from __future__ import annotations

from Delivery_app_BK.services.context import ServiceContext


def build_ctx(
    identity: dict,
    incoming_data: dict,
    *,
    prevent_event_bus: bool = True,
    on_create_return: str = "map_ids_object",
) -> ServiceContext:
    """Build a ServiceContext for test data processors.

    prevent_event_bus defaults to True to suppress order event emission
    during test data creation (avoids noise in celery queues).

    on_create_return controls what build_create_result() returns:
      - "map_ids_object" (default): dict keyed by client_id — used by most processors
      - "instances": list of SQLAlchemy model instances — used by item_property and
        item_type processors to extract the DB id directly
      - "ids": list of integer IDs
    """
    return ServiceContext(
        incoming_data=incoming_data,
        identity=identity,
        prevent_event_bus=prevent_event_bus,
        on_create_return=on_create_return,
    )


__all__ = ["build_ctx"]
```

---

## 9. `creator.py` — Dispatch Loop

```python
# test_data/creator.py
from __future__ import annotations

from typing import Any

from .registry import Registry
from .resolver import resolve_item
from .processors import (
    item_property as item_property_processor,
    item_type as item_type_processor,
    facility as facility_processor,
    vehicle as vehicle_processor,
    zone_version as zone_version_processor,
    zone as zone_processor,
    zone_template as zone_template_processor,
    route_plan as route_plan_processor,
    order as order_processor,
    order_delivery_window as order_delivery_window_processor,
    order_zone_assignment as order_zone_assignment_processor,
)

# Fixed topological processing order.
# Entities not present in the payload are silently skipped.
PROCESSING_ORDER: list[str] = [
    "item_property",      # catalog: no deps
    "item_type",          # catalog: depends on item_property (for M:N link)
    "facility",
    "vehicle",            # depends on facility
    "zone_version",
    "zone",               # depends on zone_version
    "zone_template",      # depends on zone + facility
    "route_plan",         # depends on zone (auto-creates route_groups)
    "order",              # depends on route_plan (for route_plan_id + route_group_id)
    "order_delivery_window",
    "order_zone_assignment",
]

PROCESSOR_MAP = {
    "item_property": item_property_processor.process,
    "item_type": item_type_processor.process,
    "facility": facility_processor.process,
    "vehicle": vehicle_processor.process,
    "zone_version": zone_version_processor.process,
    "zone": zone_processor.process,
    "zone_template": zone_template_processor.process,
    "route_plan": route_plan_processor.process,
    "order": order_processor.process,
    "order_delivery_window": order_delivery_window_processor.process,
    "order_zone_assignment": order_zone_assignment_processor.process,
}


def create_test_data(identity: dict, payload: dict) -> dict[str, Any]:
    """Process a JSON payload and create all described entities in topological order.

    Args:
        identity: Dict with at least team_id (or active_team_id) and user_id.
        payload: Dict mapping entity keys to lists of instance dicts.

    Returns:
        Dict with entity keys → {"count": int, "ids": [int, ...]}
    """
    registry = Registry()
    results: dict[str, Any] = {}

    for entity_key in PROCESSING_ORDER:
        items = payload.get(entity_key)
        if not items:
            continue

        if not isinstance(items, list):
            raise ValueError(f"Payload key {entity_key!r} must be a list.")

        created_ids: list[int] = []

        for index, raw_item in enumerate(items):
            if not isinstance(raw_item, dict):
                raise ValueError(
                    f"Each item in {entity_key!r} must be a dict. "
                    f"Got {type(raw_item).__name__!r} at index {index}."
                )

            # Capture metadata before resolution strips it
            sid: str | None = raw_item.get("$id")

            # For route_plan: capture zone $ids (symbolic) before resolution
            # so the processor can do positional route_group registration.
            zone_sids: list[str] = []
            if entity_key == "route_plan":
                raw_zones = raw_item.get("$zones")
                if isinstance(raw_zones, list):
                    zone_sids = [z for z in raw_zones if isinstance(z, str)]

            resolved = resolve_item(entity_key, raw_item, registry)

            # Inject internal metadata for processors that need it.
            # Keys prefixed with "_" are stripped by resolve_item and must be
            # re-injected here after resolution.
            if sid:
                resolved["_sid"] = sid
            if zone_sids:
                resolved["_zone_sids"] = zone_sids

            db_id: int = PROCESSOR_MAP[entity_key](resolved, identity, registry)

            if sid:
                registry.register(sid, db_id, entity_key)

            created_ids.append(db_id)

        results[entity_key] = {"count": len(created_ids), "ids": created_ids}

    return results


__all__ = ["create_test_data", "PROCESSING_ORDER"]
```

---

## 10. Processors

Each processor has the same signature:

```python
def process(item: dict, identity: dict, registry: Registry) -> int:
    """Create one entity instance and return its DB integer ID."""
```

- `item` — resolved dict (all `$key` refs replaced with DB IDs, `$id` stripped, `_meta` keys included for processors that need them)
- `identity` — the raw identity dict from the caller
- `registry` — the live registry (used by route_plan processor for route_group registration)

**Important:** `_sid` and `_zone_sids` are internal metadata injected by the dispatch loop. Processors that need them extract them first and remove them before building service payloads.

---

### 10.1 `processors/item_property.py`

Calls `create_item_property(ctx)`. This service uses `extract_fields(ctx)` so incoming_data must use the `{"fields": [...]}` wrapper. Uses `on_create_return="instances"` to get the model instance and extract its `id` directly.

`ItemProperty` fields accepted by `create_item_property`:
- `name` (String, required) — unique per team
- `field_type` (String) — one of: `"text"`, `"number"`, `"select"`, `"check_box"`
- `options` (list of strings) — required when `field_type == "select"`, ignored otherwise
- `required` (Boolean)
- `client_id` (String, optional — auto-generated if omitted)

```python
# test_data/processors/item_property.py
from __future__ import annotations

from Delivery_app_BK.services.commands.item.create.create_item_property import (
    create_item_property,
)
from ..context_builder import build_ctx
from ..registry import Registry


def process(item: dict, identity: dict, registry: Registry) -> int:
    fields = {k: v for k, v in item.items() if not k.startswith("_")}
    ctx = build_ctx(identity, {"fields": [fields]}, on_create_return="instances")
    result = create_item_property(ctx)
    # result is a list of ItemProperty instances (on_create_return="instances")
    return result[0].id


__all__ = ["process"]
```

---

### 10.2 `processors/item_type.py`

Calls `create_item_type(ctx)`. The `properties` field in the resolved item will already be a list of integer `ItemProperty` DB IDs (resolved from `$properties` list ref by the ref resolver). The `create_item_type` service's `relationship_map` (`"properties": ItemProperty`) handles the M:N insert into `type_property_association` automatically — no separate join processor needed.

`ItemType` fields accepted by `create_item_type`:
- `name` (String, required) — unique per team
- `properties` (list of ItemProperty integer IDs) — resolved from `$properties` list ref
- `client_id` (String, optional — auto-generated if omitted)

```python
# test_data/processors/item_type.py
from __future__ import annotations

from Delivery_app_BK.services.commands.item.create.create_item_type import (
    create_item_type,
)
from ..context_builder import build_ctx
from ..registry import Registry


def process(item: dict, identity: dict, registry: Registry) -> int:
    fields = {k: v for k, v in item.items() if not k.startswith("_")}
    ctx = build_ctx(identity, {"fields": [fields]}, on_create_return="instances")
    result = create_item_type(ctx)
    # result is a list of ItemType instances (on_create_return="instances")
    return result[0].id


__all__ = ["process"]
```

---

### 10.3 `processors/facility.py`

Uses `parse_create_facility_request` + `create_instance` exactly as the old `facility_data_creators.py` did, but without any defaults logic.

```python
# test_data/processors/facility.py
from __future__ import annotations

from Delivery_app_BK.models import Facility, db
from Delivery_app_BK.services.commands.base.create_instance import create_instance
from Delivery_app_BK.services.requests.infrastructure.facility import (
    parse_create_facility_request,
)
from ..context_builder import build_ctx
from ..registry import Registry


def process(item: dict, identity: dict, registry: Registry) -> int:
    item = {k: v for k, v in item.items() if not k.startswith("_")}
    ctx = build_ctx(identity, {})
    request = parse_create_facility_request(item)
    instance = create_instance(ctx, Facility, request.to_fields_dict())
    db.session.add(instance)
    db.session.flush()
    return instance.id


__all__ = ["process"]
```

---

### 10.4 `processors/vehicle.py`

Uses `parse_create_vehicle_request` + `create_instance`. The `home_facility_id` is already resolved from `$facility` by the ref resolver.

```python
# test_data/processors/vehicle.py
from __future__ import annotations

from Delivery_app_BK.models import Vehicle, db
from Delivery_app_BK.services.commands.base.create_instance import create_instance
from Delivery_app_BK.services.requests.infrastructure.vehicle.parse_vehicle_request import (
    parse_create_vehicle_request,
)
from ..context_builder import build_ctx
from ..registry import Registry


def process(item: dict, identity: dict, registry: Registry) -> int:
    item = {k: v for k, v in item.items() if not k.startswith("_")}
    ctx = build_ctx(identity, {})
    request = parse_create_vehicle_request(item)
    instance = create_instance(ctx, Vehicle, request.to_fields_dict())
    db.session.add(instance)
    db.session.flush()
    return instance.id


__all__ = ["process"]
```

---

### 10.5 `processors/zone_version.py`

Calls `create_zone_version(ctx)`. The function reads `city_key` directly from `ctx.incoming_data` (no `fields` wrapper needed — `create_zone_version` uses `ctx.incoming_data.get("city_key")` directly).

```python
# test_data/processors/zone_version.py
from __future__ import annotations

from Delivery_app_BK.services.commands.zones.create_zone_version import create_zone_version
from ..context_builder import build_ctx
from ..registry import Registry


def process(item: dict, identity: dict, registry: Registry) -> int:
    item = {k: v for k, v in item.items() if not k.startswith("_")}
    ctx = build_ctx(identity, item)
    result = create_zone_version(ctx)
    return result["id"]


__all__ = ["process"]
```

---

### 10.6 `processors/zone.py`

Calls `create_zone(ctx)`. The function reads `version_id`, `name`, `zone_type` etc. directly from `ctx.incoming_data`. The `version_id` field is already resolved from `$zone_version` by the ref resolver (see `ref_map.py`: `"$zone_version": "version_id"`).

```python
# test_data/processors/zone.py
from __future__ import annotations

from Delivery_app_BK.services.commands.zones.create_zone import create_zone
from ..context_builder import build_ctx
from ..registry import Registry


def process(item: dict, identity: dict, registry: Registry) -> int:
    item = {k: v for k, v in item.items() if not k.startswith("_")}
    ctx = build_ctx(identity, item)
    result = create_zone(ctx)
    return result["id"]


__all__ = ["process"]
```

---

### 10.7 `processors/zone_template.py`

Calls `create_zone_template(ctx)`. Reads `zone_id` and `version_id` from `ctx.incoming_data` plus all template fields. The `zone_id` is resolved from `$zone` and `default_facility_id` from `$facility` by the ref resolver.

```python
# test_data/processors/zone_template.py
from __future__ import annotations

from Delivery_app_BK.services.commands.zones.create_zone_template import create_zone_template
from ..context_builder import build_ctx
from ..registry import Registry


def process(item: dict, identity: dict, registry: Registry) -> int:
    item = {k: v for k, v in item.items() if not k.startswith("_")}
    ctx = build_ctx(identity, item)
    result = create_zone_template(ctx)
    return result["id"]


__all__ = ["process"]
```

---

### 10.8 `processors/route_plan.py` ← Key processor

This is the most complex processor. It:
1. Calls the live `create_plan` service (unchanged)
2. Auto-registers the created route_groups using positional mapping
3. Returns the plan DB ID

**Critical facts about `create_plan`:**
- Expects `ctx.incoming_data = {"fields": [plan_dict]}` because it uses `extract_fields(ctx)` internally, which requires a `"fields"` key.
- `plan_dict` allowed fields: `client_id`, `label`, `date_strategy`, `start_date`, `end_date`, `order_ids`, `zone_ids`, `route_group_defaults`. NOTHING ELSE — the request parser validates unexpected fields.
- Does NOT accept `plan_type`. The `plan_type` was only in the old test_data system's internal `create_plan_bundle`. The live `create_plan` creates a local_delivery plan always (it creates `RouteGroup` + `RouteSolution`).
- Returns `{"created": [{"delivery_plan": {...}, "route_groups": [...], "route_solutions": [...]}]}`

**Critical facts about route_group creation order:**
- `create_plan` creates the **no-zone default bucket first** (`is_system_default_bucket=True`), then one group per zone_id in the same order as `zone_ids` was passed.
- The `serialize_created_route_group` serializer does NOT include `zone_id` or `is_system_default_bucket`. So we cannot read those fields from the returned dicts.
- We use **positional mapping** instead: `bundle["route_groups"][0]` = default bucket, `bundle["route_groups"][i+1]` = zone at `zone_ids[i]`.
- `_zone_sids` injected by the dispatch loop holds the original symbolic zone IDs in the same order as `zone_ids` was resolved — this gives us the stable names.

```python
# test_data/processors/route_plan.py
from __future__ import annotations

from Delivery_app_BK.services.commands.route_plan.create_plan import create_plan
from ..context_builder import build_ctx
from ..registry import Registry

# Fields allowed by parse_create_plan_request — strip everything else
# so the live service's field validator does not reject the request.
_ALLOWED_PLAN_FIELDS = frozenset({
    "client_id",
    "label",
    "date_strategy",
    "start_date",
    "end_date",
    "order_ids",
    "zone_ids",
    "route_group_defaults",
})


def process(item: dict, identity: dict, registry: Registry) -> int:
    # Extract internal metadata (not sent to create_plan)
    sid: str | None = item.get("_sid")
    zone_sids: list[str] = item.get("_zone_sids", [])

    # Build the clean plan payload — only allowed fields
    plan_fields = {k: v for k, v in item.items() if k in _ALLOWED_PLAN_FIELDS}

    ctx = build_ctx(identity, {"fields": [plan_fields]})
    result = create_plan(ctx)

    bundle = result["created"][0]
    plan_id: int = bundle["delivery_plan"]["id"]
    route_groups: list[dict] = bundle.get("route_groups", [])

    # Auto-register route_groups in the registry using positional mapping.
    # create_plan always creates groups in this exact order:
    #   index 0 → no-zone default bucket
    #   index 1 → zone_sids[0]
    #   index 2 → zone_sids[1]
    #   ...
    if sid and route_groups:
        default_rg = route_groups[0]
        registry.register(f"{sid}.rg.default", default_rg["id"])

        for i, zone_sid in enumerate(zone_sids):
            zone_rg_index = i + 1
            if zone_rg_index < len(route_groups):
                registry.register(
                    f"{sid}.rg.{zone_sid}",
                    route_groups[zone_rg_index]["id"],
                )

    return plan_id


__all__ = ["process"]
```

---

### 10.9 `processors/order.py`

Calls `create_order(ctx)` with the resolved fields. The `route_plan_id` and `route_group_id` are already resolved from `$route_plan` and `$route_group` by the ref resolver and will be included in the fields dict.

`create_order` uses `extract_fields(ctx)` internally, so the incoming_data must be `{"fields": [order_fields]}`.

`create_order` internally handles stop creation via `apply_order_plan_objective`, so you do NOT need to call `apply_orders_route_plan_change` separately.

**Items are passed inline.** The `items` array is part of the order fields dict and is handled by `create_order`'s request parser directly. Each item dict uses plain string values — `item_type` is a string name (e.g. `"test-Vintage Chair"`), and `properties` is a list of `{"name": "...", "value": "..."}` dicts. **There is no `$ref` expansion for inline items.** The caller writes the type name string directly.

Allowed item fields (from `ITEM_ALLOWED_FIELDS` in `services/requests/order/create_order.py`):
`article_number` (required), `reference_number`, `item_type`, `properties`, `quantity`, `item_position_id`, `item_state_id`, `page_link`, `dimension_depth`, `dimension_height`, `dimension_width`, `weight`

**Delivery windows are also passed inline** via `delivery_windows` in the order dict (preferred over using the separate `order_delivery_window` entity). Each window requires `start_at`, `end_at`, and `window_type`.

```python
# test_data/processors/order.py
from __future__ import annotations

from Delivery_app_BK.services.commands.order.create_order import create_order
from ..context_builder import build_ctx
from ..registry import Registry


def process(item: dict, identity: dict, registry: Registry) -> int:
    order_fields = {k: v for k, v in item.items() if not k.startswith("_")}
    ctx = build_ctx(identity, {"fields": [order_fields]})
    result = create_order(ctx)
    # create_order returns {"created": [{"order": {"id": ...}, ...}]}
    return result["created"][0]["order"]["id"]


__all__ = ["process"]
```

**Note:** If `create_order`'s return shape is different, check `serialize_created_order` in `services/commands/order/create_serializers.py`. Adapt the ID extraction accordingly. The key is getting the created order's integer `id`.

---

### 10.10 `processors/order_delivery_window.py`

`OrderDeliveryWindow` is typically created inline during `create_order` via the `delivery_windows` field. However, if you need to create a delivery window post-order, use `create_instance` directly.

Check whether your codebase has a `create_order_delivery_window` service. If not, use:

```python
# test_data/processors/order_delivery_window.py
from __future__ import annotations

from Delivery_app_BK.models import OrderDeliveryWindow, db
from Delivery_app_BK.services.commands.base.create_instance import create_instance
from ..context_builder import build_ctx
from ..registry import Registry


def process(item: dict, identity: dict, registry: Registry) -> int:
    fields = {k: v for k, v in item.items() if not k.startswith("_")}
    ctx = build_ctx(identity, {})
    instance = create_instance(ctx, OrderDeliveryWindow, fields)
    db.session.add(instance)
    db.session.flush()
    return instance.id


__all__ = ["process"]
```

---

### 10.11 `processors/order_zone_assignment.py`

Similar pattern — use `create_instance` directly if no dedicated service exists.

```python
# test_data/processors/order_zone_assignment.py
from __future__ import annotations

from Delivery_app_BK.models import OrderZoneAssignment, db
from Delivery_app_BK.services.commands.base.create_instance import create_instance
from ..context_builder import build_ctx
from ..registry import Registry


def process(item: dict, identity: dict, registry: Registry) -> int:
    fields = {k: v for k, v in item.items() if not k.startswith("_")}
    ctx = build_ctx(identity, {})
    instance = create_instance(ctx, OrderZoneAssignment, fields)
    db.session.add(instance)
    db.session.flush()
    return instance.id


__all__ = ["process"]
```

---

### 10.12 `processors/__init__.py`

Empty. Import processors by submodule in `creator.py`.

---

## 11. `cleanup.py` (modified)

The current `cleanup.py` deletes by plan label and order reference prefix. This is kept but the `TEST_PLAN_LABELS` constant that it imported from the deleted `config/plan_defaults.py` must be replaced with an inline constant or removed.

The simplest approach: make `TEST_PLAN_LABELS` an empty dict by default and let callers pass their own plan labels via `additional_plan_labels`. The cleanup function signature and logic stay the same — just remove the import from the deleted config module.

```python
# Replace this at the top of cleanup.py:
from .config import TEST_PLAN_LABELS

# With this:
TEST_PLAN_LABELS: dict[str, set[str]] = {}
```

Everything else in `cleanup.py` stays identical. Callers who want to clean up specific plans pass the labels via `additional_plan_labels` in the incoming_data.

---

## 12. `__init__.py` — Public API

```python
# test_data/__init__.py
from .creator import create_test_data
from .cleanup import clear_generated_test_data

__all__ = ["create_test_data", "clear_generated_test_data"]
```

The old `__init__.py` exported 18 names. The new one exports 2.

---

## 13. Live Services Used (Do Not Modify These)

These are production services. The test data processors call them as-is. Do not change their signatures or behavior.

| Service | File | Called by processor |
|---------|------|---------------------|
| `create_item_property(ctx)` | `services/commands/item/create/create_item_property.py` | item_property |
| `create_item_type(ctx)` | `services/commands/item/create/create_item_type.py` | item_type |
| `create_zone_version(ctx)` | `services/commands/zones/create_zone_version.py` | zone_version |
| `create_zone(ctx)` | `services/commands/zones/create_zone.py` | zone |
| `create_zone_template(ctx)` | `services/commands/zones/create_zone_template.py` | zone_template |
| `create_plan(ctx)` | `services/commands/route_plan/create_plan.py` | route_plan |
| `create_order(ctx)` | `services/commands/order/create_order.py` | order |
| `parse_create_facility_request` | `services/requests/infrastructure/facility` | facility |
| `parse_create_vehicle_request` | `services/requests/infrastructure/vehicle/parse_vehicle_request.py` | vehicle |
| `create_instance(ctx, Model, fields)` | `services/commands/base/create_instance.py` | facility, vehicle, order_delivery_window, order_zone_assignment |

### How each service reads its inputs

| Service | Input pattern |
|---------|--------------|
| `create_item_property` | `extract_fields(ctx)` — requires `ctx.incoming_data = {"fields": [property_dict]}` |
| `create_item_type` | `extract_fields(ctx)` — requires `ctx.incoming_data = {"fields": [type_dict]}` |
| `create_zone_version` | `ctx.incoming_data.get("city_key")` — direct dict read |
| `create_zone` | `ctx.incoming_data.get("version_id")`, `.get("name")`, etc. — direct dict read |
| `create_zone_template` | `ctx.incoming_data.get("zone_id")`, etc. — direct dict read |
| `create_plan` | `extract_fields(ctx)` — requires `ctx.incoming_data = {"fields": [plan_dict]}` |
| `create_order` | `extract_fields(ctx)` — requires `ctx.incoming_data = {"fields": [order_dict]}` |

This distinction is critical. `create_item_property`, `create_item_type`, `create_plan`, and `create_order` WILL raise `ValidationFailed("Missing key 'fields' in request payload.")` if you pass the dict directly without the `fields` wrapper.

### `create_item_type` relationship_map and M:N join

`create_item_type` sets its own `relationship_map = {"properties": ItemProperty, "team_id": Team}` internally before calling `create_instance`. This means when the `fields` dict contains `"properties": [101, 102]`, `create_instance` queries those `ItemProperty` IDs and inserts rows into `type_property_association`. You do not need to manage the join table yourself — just pass the resolved integer IDs.

---

## 14. `ServiceContext` Construction

```python
class ServiceContext:
    def __init__(
        self,
        incoming_data=None,       # dict passed to the service
        incoming_file=None,       # unused by test data
        query_params=None,        # unused by test data
        identity=None,            # dict: {team_id/active_team_id, user_id, ...}
        check_team_id=True,
        inject_team_id=True,
        skip_id_instance_injection=True,
        relationship_map=None,
        on_create_return="map_ids_object",
        on_query_return="client_ids_map",
        allow_is_system_modification=False,
        extract_fields_key=True,  # True = extract_fields() requires "fields" key
        prevent_event_bus=False,
    )

    @property
    def team_id(self):
        return self.identity.get("active_team_id", self.identity.get("team_id"))

    @property
    def user_id(self):
        return self.identity.get("user_id")

    @property
    def default_city_key(self):
        return self.identity.get("default_city_key")
```

The `identity` dict must contain at minimum:
```python
{
    "team_id": 5,          # or "active_team_id": 5
    "user_id": 1,
}
```

Optional fields that services may read:
```python
{
    "time_zone": "Europe/Stockholm",
    "default_country_code": "SE",
    "default_city_key": "stockholm",
}
```

---

## 15. Router Integration

The existing router that triggers test data generation is at:
```
Delivery_app_BK/routers/api_v2/...   # (find the route that calls generate_plan_and_order_test_data)
```

After this refactor:
- The router imports `create_test_data` from the new `test_data/__init__.py`
- The router extracts `identity` from the auth context (same as before)
- The router reads the `payload` from `request.json` and passes it directly to `create_test_data`
- No orchestration logic in the router — just `create_test_data(identity, payload)`

Check the existing router file and update its import + call site. The test data router probably calls `generate_plan_and_order_test_data(ctx)` today — replace that with `create_test_data(ctx.identity, ctx.incoming_data)`.

---

## 16. Test Plan

### Unit tests — pure functions (no DB, no mocks of real modules)

#### `tests/unit/services/commands/test_data/test_registry.py`

Test cases:
- `test_register_and_resolve` — register a sid, resolve it, get the DB id back
- `test_resolve_unregistered_raises` — calling resolve() for unknown sid raises `RefResolutionError`
- `test_duplicate_sid_overwrites` — registering same sid twice uses the latest value
- `test_reverse_lookup` — register with entity_key, reverse_lookup returns sid
- `test_reverse_lookup_unknown_raises` — reverse_lookup for unknown entity/db_id raises `RefResolutionError`
- `test_is_registered` — returns True after register, False before

#### `tests/unit/services/commands/test_data/test_resolver.py`

Test cases:
- `test_strips_dollar_id` — `$id` key is not present in output
- `test_strips_underscore_keys` — `_sid`, `_zone_sids` are not in output
- `test_resolves_scalar_ref` — `$facility: "f1"` → `home_facility_id: 101`
- `test_resolves_list_ref` — `$zones: ["z1", "z2"]` → `zone_ids: [101, 102]`
- `test_unknown_dollar_key_raises` — unknown `$ref` raises `RefResolutionError`
- `test_unresolvable_sid_raises` — ref to unregistered sid raises `RefResolutionError` with entity context
- `test_passthrough_non_ref_keys` — plain keys (no `$`) are passed through unchanged
- `test_entity_with_no_ref_rules` — entity not in REF_FIELD_MAP passes through cleanly

#### `tests/unit/services/commands/test_data/test_creator.py`

Use `monkeypatch` to replace all processor `process` functions with fakes that record calls and return sequential IDs. Verify:
- `test_processes_entities_in_topological_order` — item_property before item_type, facility before vehicle, zone_version before zone before zone_template, zone before route_plan, route_plan before order
- `test_skips_missing_entity_keys` — payload with only "facility" key does not call other processors
- `test_registers_sid_after_create` — after facility processor returns 101, subsequent `$facility: "f1"` in vehicle resolves to 101
- `test_returns_count_and_ids` — result dict has correct count and id list per entity
- `test_route_plan_receives_zone_sids` — `_zone_sids` metadata is injected into the item before calling route_plan processor
- `test_rejects_non_list_entity_value` — `{"facility": {}}` (dict not list) raises ValueError

### Unit tests — processors (monkeypatch the underlying service call)

#### `processors/test_item_property.py`

- `test_process_calls_create_item_property_with_fields_wrapper` — confirms `{"fields": [fields_dict]}` is passed to the service
- `test_process_returns_db_id` — fake service returns a mock instance with `.id = 55`, process() returns 55
- `test_process_strips_underscore_keys` — `_sid` key is not forwarded to the service

#### `processors/test_item_type.py`

- `test_process_calls_create_item_type_with_resolved_properties` — confirms `properties: [101, 102]` (already resolved ints) is passed in the fields dict
- `test_process_returns_db_id` — returns the id of the created instance
- `test_process_with_no_properties` — empty `$properties` resolved to `properties: []` — service is called with empty list

Each processor test follows the same pattern:

```python
from types import SimpleNamespace
import pytest
from Delivery_app_BK.services.commands.test_data.processors import facility as module

def test_process_calls_service_and_returns_id(monkeypatch):
    calls = []
    def fake_parse(payload):
        calls.append(payload)
        return SimpleNamespace(to_fields_dict=lambda: {"name": "Test", "team_id": 5})
    def fake_create_instance(ctx, model, fields):
        instance = SimpleNamespace()
        instance.id = 42
        return instance
    monkeypatch.setattr(module, "parse_create_facility_request", fake_parse)
    monkeypatch.setattr(module, "create_instance", fake_create_instance)
    monkeypatch.setattr(module.db.session, "add", lambda x: None)
    monkeypatch.setattr(module.db.session, "flush", lambda: None)

    result = module.process({"name": "Test"}, {"team_id": 5, "user_id": 1}, None)
    assert result == 42
    assert calls[0]["name"] == "Test"
```

#### `processors/test_route_plan.py` — extra cases

- `test_auto_registers_default_route_group` — registry contains `"p1.rg.default"` after creation
- `test_auto_registers_zone_route_groups` — registry contains `"p1.rg.z1"` and `"p1.rg.z2"` in correct positional order
- `test_strips_internal_metadata_from_plan_fields` — `_sid` and `_zone_sids` are NOT passed to create_plan
- `test_strips_unknown_fields_from_plan_fields` — only allowed plan fields are forwarded
- `test_only_registers_if_sid_provided` — if no `$id` on plan, route_groups are still created but not registered

---

## 17. Implementation Order

Implement in this sequence to maintain a testable state at each step:

**Step 1 — Infrastructure (no DB dependency)**
Create `registry.py`, `ref_map.py`, `resolver.py`, `context_builder.py`.
Write `test_registry.py` and `test_resolver.py`. All tests should pass with no DB.

**Step 2 — Simple processors (parallel)**
Create `processors/item_property.py`, `processors/item_type.py`, `processors/facility.py`, `processors/vehicle.py`, `processors/zone_version.py`, `processors/zone.py`, `processors/zone_template.py`, `processors/order_delivery_window.py`, `processors/order_zone_assignment.py`.
Write their unit tests with monkeypatched service calls.

**Step 3 — Complex processors**
Create `processors/route_plan.py` and `processors/order.py`.
Write `processors/test_route_plan.py` and `processors/test_order.py`.

**Step 4 — Dispatch loop + public API**
Create `creator.py`, update `__init__.py`.
Write `test_creator.py`.

**Step 5 — Cleanup + router update**
Modify `cleanup.py` (remove config import, inline empty `TEST_PLAN_LABELS`).
Update the router import + call site.

**Step 6 — Delete old files**
Delete all files listed in Section 2.

**Step 7 — Run tests**
```bash
pytest tests/unit/services/commands/test_data/ -v
```

---

## 18. Gotchas and Edge Cases

### `ItemType` and `ItemProperty` are catalog only — `Item.item_type` is a string

`Item.item_type` is `Column(String)` — a plain text snapshot, not a FK to `ItemType`. The same applies to `Item.properties` which is `JSONB`. This means order items are denormalized at creation time and are not linked to the catalog by a DB constraint. When writing order items in the payload, copy the type name string directly:
```json
"items": [{ "article_number": "X1", "item_type": "test-Vintage Chair", "quantity": 2 }]
```
The `ItemType`/`ItemProperty` catalog exists purely for the UI to offer a picker. Deleting a catalog entry does not affect existing order items.

### `ItemProperty.field_type` must be one of four values

The `ItemProperty` model has a `@validates("field_type")` SQLAlchemy validator that raises `ValueError` if the value is not in `{"text", "number", "select", "check_box"}`. The `options` field is only meaningful (and required) when `field_type == "select"`. For other types, omit `options` or pass `null`.

### `create_item_property` and `create_item_type` require `"fields"` wrapper

Same as `create_plan` — both use `extract_fields(ctx)`. Pass `{"fields": [fields_dict]}` as `incoming_data`.

### `create_plan` requires `"fields"` wrapper
```python
# WRONG — will raise ValidationFailed("Missing key 'fields' ...")
ctx = build_ctx(identity, {"label": "Plan A", "start_date": "..."})
create_plan(ctx)

# CORRECT
ctx = build_ctx(identity, {"fields": [{"label": "Plan A", "start_date": "..."}]})
create_plan(ctx)
```

### `create_plan` rejects unexpected fields
`parse_create_plan_request` validates against `ALLOWED_CREATE_FIELDS`. Do NOT pass `plan_type`, `team_id`, `state_id`, or any other field not in:
```python
{"client_id", "label", "date_strategy", "start_date", "end_date", "order_ids", "zone_ids", "route_group_defaults"}
```

### `create_plan` does not produce `plan_type`
The live `create_plan` creates a local_delivery-style plan (RouteGroup + RouteSolution). If you need a `store_pickup` or `international_shipping` plan structure, this requires a different service or direct row creation — those are out of scope for this refactor.

### `create_zone` calls `db.session.commit()` internally
`create_zone` and `create_zone_template` and `create_zone_version` call `db.session.commit()` directly. This is a quirk of those services. Do not wrap calls to them inside an explicit transaction (`db.session.begin()`). The `create_plan` service uses `with db.session.begin()` internally. These are pre-existing behaviors — do not modify them.

### Route group positional mapping assumes fixed creation order
The positional mapping in `route_plan.py` processor depends on `create_plan` always creating the no-zone group first (index 0), then zone groups in `zone_ids` order (indices 1..N). This is verified by reading `create_plan.py` line by line:
1. `_build_no_zone_route_group_instance` called first → `entry["route_groups"].append(no_zone_group)` (index 0)
2. `_build_zone_route_group_instances` called next → `entry["route_groups"].extend(zone_groups)` (indices 1..N)

If `create_plan.py` is ever refactored to change this order, the positional mapping must be updated.

### `serialize_created_route_group` does not include `zone_id`
The serialized route_group dict from `create_plan` contains: `id`, `client_id`, `route_plan_id`, `state_id`, `total_weight_g`, `total_volume_cm3`, `total_item_count`, `total_orders`, `order_state_counts`. It does NOT include `zone_id` or `is_system_default_bucket`. This is why positional mapping is used instead of field-based lookup.

### `$zones` is a list ref — the only one
All other `$ref` keys are scalar. `$zones` is the only list ref in the system. The resolver handles it via the `("zone_ids", "list")` tuple in `REF_FIELD_MAP`. If you add more list refs later, add them using the same tuple pattern.

### Route group names use the plan's `$id`, not its DB id
`"p1.rg.z1"` uses the symbolic `$id` "p1", not the integer DB id 42. This keeps references human-readable in the payload.

### `preferred_vehicle_ids` on `zone_template` is a raw integer list
You cannot use `$ref` notation for this field. Pass DB integer IDs directly:
```json
{ "$zone": "z1", "$facility": "f1", "preferred_vehicle_ids": [101, 102] }
```
If you need symbolic refs here, it requires extending the resolver with per-key list-ref support — defer until needed.

---

## 19. Complete File Reference

### Files in `test_data/` after refactor

| File | Lines (est.) | Responsibility |
|------|-------------|----------------|
| `__init__.py` | ~5 | Public API |
| `creator.py` | ~85 | Dispatch loop, PROCESSING_ORDER |
| `registry.py` | ~65 | Forward + reverse ID maps |
| `ref_map.py` | ~40 | Declarative $key → FK column |
| `resolver.py` | ~65 | resolve_item() pure function |
| `context_builder.py` | ~25 | build_ctx() helper (with on_create_return param) |
| `cleanup.py` | ~90 | Delete test data by label/prefix (modified) |
| `processors/__init__.py` | ~1 | Empty |
| `processors/item_property.py` | ~20 | create_item_property(ctx) — item catalog property |
| `processors/item_type.py` | ~20 | create_item_type(ctx) — item catalog type + M:N link |
| `processors/facility.py` | ~20 | parse_create_facility_request + create_instance |
| `processors/vehicle.py` | ~20 | parse_create_vehicle_request + create_instance |
| `processors/zone_version.py` | ~15 | create_zone_version(ctx) |
| `processors/zone.py` | ~15 | create_zone(ctx) |
| `processors/zone_template.py` | ~15 | create_zone_template(ctx) |
| `processors/route_plan.py` | ~55 | create_plan(ctx) + route_group registration |
| `processors/order.py` | ~20 | create_order(ctx) — items + delivery_windows inline |
| `processors/order_delivery_window.py` | ~20 | create_instance (post-creation windows only) |
| `processors/order_zone_assignment.py` | ~20 | create_instance |

### Tests in `tests/unit/services/commands/test_data/` after refactor

| File | Responsibility |
|------|---------------|
| `test_registry.py` | Registry forward/reverse maps |
| `test_resolver.py` | resolve_item() pure function |
| `test_creator.py` | Dispatch loop with all processors monkeypatched |
| `processors/test_item_property.py` | item_property.process() — fields wrapper, id extraction |
| `processors/test_item_type.py` | item_type.process() — resolved properties list, M:N via service |
| `processors/test_facility.py` | facility.process() |
| `processors/test_vehicle.py` | vehicle.process() |
| `processors/test_zone_version.py` | zone_version.process() |
| `processors/test_zone.py` | zone.process() |
| `processors/test_zone_template.py` | zone_template.process() |
| `processors/test_route_plan.py` | route_plan.process() + registry auto-population |
| `processors/test_order.py` | order.process() |
| `processors/test_order_delivery_window.py` | order_delivery_window.process() |
| `processors/test_order_zone_assignment.py` | order_zone_assignment.process() |
