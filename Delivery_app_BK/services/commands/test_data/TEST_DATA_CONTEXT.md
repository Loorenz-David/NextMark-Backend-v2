# Test Data Context

## Purpose

This folder contains the JSON-driven test data creation system for:

- item property and item type catalogs
- facilities and vehicles
- zone versions, zones, and zone templates
- route plans and their auto-created route groups
- orders, inline items, delivery windows, and optional zone assignments

The system is centered on:

```python
create_test_data(identity: dict, payload: dict) -> dict
```

The caller describes exactly what to create in JSON. There are no config defaults and no orchestration presets anymore.

The system also applies a test-data client-id namespace so cleanup can target created rows across repeated runs and server restarts.

---

## Public API

Exports from `Delivery_app_BK/services/commands/test_data/__init__.py`:

- `create_test_data`
- `clear_generated_test_data`

The seed router calls:

```python
create_test_data(ctx.identity, ctx.incoming_data)
```

Current seed route:

- `POST /api_v2/seed/test-data`

Cleanup routes:

- `POST /api_v2/seed/test-data/cleanup`
- `DELETE /api_v2/seed/test-data`

---

## Architecture

### Entry point

- `creator.py`

Responsibilities:

- enforce fixed topological processing order
- validate each top-level payload key is a list
- reject unknown top-level payload keys except `_meta`
- resolve symbolic `$ref` values before processor execution
- inject internal metadata needed by specific processors
- collect created DB ids per entity type

### Core infrastructure

- `registry.py`
  - stores symbolic `$id` to DB id mappings
  - supports reverse lookup when needed
- `ref_map.py`
  - declarative mapping from `$key` to destination field name
- `resolver.py`
  - strips `$id`
  - strips `_...` internal metadata keys
  - resolves `$ref` keys to DB integer ids
- `context_builder.py`
  - creates `ServiceContext` instances for processors

### Processors

Processors live in `processors/` and each implements:

```python
def process(item: dict, identity: dict, registry: Registry) -> int:
    ...
```

Implemented processors:

- `item_property.py`
- `item_type.py`
- `facility.py`
- `vehicle.py`
- `zone_version.py`
- `zone.py`
- `zone_template.py`
- `route_plan.py`
- `order.py`
- `order_delivery_window.py`
- `order_zone_assignment.py`

Each processor adapts the resolved payload to an existing live service or `create_instance(...)`.

### Cleanup

- `cleanup.py`

Cleanup remains prefix/label based and no longer depends on deleted config modules. `TEST_PLAN_LABELS` is intentionally empty by default.
Cleanup now also supports client-id-prefix deletion for entities that carry `client_id`.

---

## Processing Order

Processing order is fixed in `creator.py`:

1. `item_property`
2. `item_type`
3. `facility`
4. `vehicle`
5. `zone_version`
6. `zone`
7. `zone_template`
8. `route_plan`
9. `order`
10. `order_delivery_window`
11. `order_zone_assignment`

This means JSON key order does not matter as long as referenced entities exist somewhere in the payload and are handled earlier in the internal order.

---

## Payload Model

`payload` is a flat object whose top-level keys are entity types.

Example shape:

```json
{
  "facility": [
    {
      "$id": "f1",
      "name": "Kista Depot",
      "facility_type": "warehouse",
      "can_dispatch": true,
      "property_location": {
        "lat": 59.403,
        "lng": 17.927,
        "address": "Kista, Stockholm"
      }
    }
  ],
  "vehicle": [
    {
      "$id": "v1",
      "$facility": "f1",
      "label": "Van 1",
      "registration_number": "ABC-001"
    }
  ]
}
```

Rules:

- each top-level entity key maps to a list
- each list item must be an object
- `$id` is a symbolic alias used only inside the payload
- `$something` means a symbolic reference that is resolved to a DB id before processor execution
- unknown top-level entity keys raise `ValueError`
- unknown `$ref` keys raise `RefResolutionError`
- missing referenced `$id`s raise `RefResolutionError`

Optional top-level meta:

```json
{
  "_meta": {
    "client_id_prefix": "td:"
  }
}
```

`client_id_prefix` defaults to `td:` when omitted.

---

## Reference Rules

### Scalar refs

Examples:

- `vehicle.$facility` -> `home_facility_id`
- `zone.$zone_version` -> `version_id`
- `zone_template.$zone` -> `zone_id`
- `zone_template.$facility` -> `default_facility_id`
- `order.$route_plan` -> `route_plan_id`
- `order.$route_group` -> `route_group_id`

### List refs

Implemented list refs:

- `item_type.$properties` -> `properties`
- `route_plan.$zones` -> `zone_ids`

Example:

```json
{
  "item_property": [
    { "$id": "ip_color", "name": "test-Color", "field_type": "text", "required": false }
  ],
  "item_type": [
    {
      "$id": "it_chair",
      "name": "test-Chair",
      "$properties": ["ip_color"]
    }
  ]
}
```

---

## Route Plan and Route Group Refs

`route_plan.py` creates the plan by calling the live `create_plan(...)` service.

That live service auto-creates route groups in this order:

1. default no-zone bucket
2. one route group per `zone_id`, in the same order as `zone_ids`

The processor registers stable symbolic route-group refs:

- `{plan_sid}.rg.default`
- `{plan_sid}.rg.{zone_sid}`

Example:

```json
{
  "zone": [
    { "$id": "z1", "$zone_version": "zv1", "name": "North", "zone_type": "user" }
  ],
  "route_plan": [
    {
      "$id": "p1",
      "$zones": ["z1"],
      "label": "Monday Plan",
      "start_date": "2026-04-01T00:00:00Z",
      "end_date": "2026-04-01T23:59:59Z"
    }
  ],
  "order": [
    {
      "$id": "o1",
      "$route_plan": "p1",
      "$route_group": "p1.rg.z1",
      "reference_number": "test-001",
      "operation_type": "dropoff",
      "order_plan_objective": "local_delivery"
    }
  ]
}
```

---

## Order Item Model

Order items are denormalized snapshots.

Important:

- `Item.item_type` is a string column, not a foreign key to `ItemType`
- `Item.properties` is JSON, not a relational link
- `items[].article_number` is required by the live order parser

So inline order items must use plain values:

```json
{
  "order": [
    {
      "reference_number": "test-001",
      "operation_type": "dropoff",
      "order_plan_objective": "local_delivery",
      "items": [
        {
          "article_number": "CHAIR-001",
          "item_type": "test-Chair",
          "quantity": 2,
          "weight": 12000,
          "properties": [
            { "name": "test-Color", "value": "Oak Brown" }
          ]
        }
      ]
    }
  ]
}
```

There is no `$ref` expansion inside `items`.

Inline order items and inline delivery windows receive generated `client_id` values automatically inside the test-data namespace.

---

## Delivery Windows

Preferred approach: pass delivery windows inline on the order.

Example:

```json
{
  "order": [
    {
      "reference_number": "test-001",
      "operation_type": "dropoff",
      "order_plan_objective": "local_delivery",
      "delivery_windows": [
        {
          "start_at": "2026-04-01T09:00:00Z",
          "end_at": "2026-04-01T17:00:00Z",
          "window_type": "TIME_RANGE"
        }
      ]
    }
  ]
}
```

`order_delivery_window` exists only for post-creation cases where a window is created separately.

---

## Identity Requirements

`identity` should contain at minimum:

```python
{
    "team_id": 5,
    "user_id": 1,
}
```

Also supported:

```python
{
    "active_team_id": 5,
    "time_zone": "Europe/Stockholm",
    "default_country_code": "SE",
    "default_city_key": "stockholm",
}
```

`ServiceContext.team_id` resolves from `active_team_id` first, then `team_id`.

---

## Minimal End-to-End Example

```json
{
  "item_property": [
    { "$id": "ip_color", "name": "test-Color", "field_type": "text", "required": false }
  ],
  "item_type": [
    { "$id": "it_chair", "name": "test-Chair", "$properties": ["ip_color"] }
  ],
  "facility": [
    {
      "$id": "f1",
      "name": "Kista Depot",
      "facility_type": "warehouse",
      "can_dispatch": true,
      "property_location": {
        "lat": 59.403,
        "lng": 17.927,
        "address": "Kista, Stockholm"
      }
    }
  ],
  "vehicle": [
    {
      "$id": "v1",
      "$facility": "f1",
      "label": "Van 1",
      "registration_number": "ABC-001"
    }
  ],
  "zone_version": [
    { "$id": "zv1", "city_key": "stockholm" }
  ],
  "zone": [
    { "$id": "z1", "$zone_version": "zv1", "name": "North Zone", "zone_type": "user" }
  ],
  "zone_template": [
    {
      "$zone": "z1",
      "$facility": "f1",
      "name": "North Zone Template",
      "default_route_end_strategy": "round_trip"
    }
  ],
  "route_plan": [
    {
      "$id": "p1",
      "$zones": ["z1"],
      "label": "Monday Plan",
      "start_date": "2026-04-01T00:00:00Z",
      "end_date": "2026-04-01T23:59:59Z"
    }
  ],
  "order": [
    {
      "$id": "o1",
      "$route_plan": "p1",
      "$route_group": "p1.rg.z1",
      "reference_number": "test-001",
      "client_first_name": "Erik",
      "client_last_name": "Svensson",
      "client_address": {
        "lat": 59.41,
        "lng": 17.93,
        "address": "Kista 1, Stockholm"
      },
      "operation_type": "dropoff",
      "order_plan_objective": "local_delivery",
      "items": [
        {
          "article_number": "CHAIR-001",
          "item_type": "test-Chair",
          "quantity": 2,
          "weight": 12000,
          "properties": [
            { "name": "test-Color", "value": "Oak Brown" }
          ]
        }
      ],
      "delivery_windows": [
        {
          "start_at": "2026-04-01T09:00:00Z",
          "end_at": "2026-04-01T17:00:00Z",
          "window_type": "TIME_RANGE"
        }
      ]
    }
  ]
}
```

---

## Result Shape

`create_test_data(...)` returns:

```python
{
    "facility": {"count": 1, "ids": [101]},
    "vehicle": {"count": 1, "ids": [201]},
    "route_plan": {"count": 1, "ids": [301]},
    "order": {"count": 1, "ids": [401]},
}
```

Only entity types present in the payload appear in the result.

---

## Client ID Namespace

For entities that support `client_id`, the test-data system assigns namespaced values so cleanup can remove them later.

Default namespace:

```text
td:
```

Examples:

- `td:facility:f1:<uuid>`
- `td:vehicle:v1:<uuid>`
- `td:route_plan:p1:<uuid>`
- `td:order:o1:<uuid>`
- `td:item:item_0:<uuid>`

This applies both to explicit payload rows and to nested rows created inside live services when those services generate `client_id` values through the shared generator.

---

## Cleanup API

Cleanup removes seeded test data for a team.

Accepted cleanup knobs:

- `order_reference_prefix`
- `item_name_prefix`
- `additional_plan_labels`
- `client_id_prefix`

Defaults:

- `order_reference_prefix = "test-"`
- `item_name_prefix = "test-"`
- `client_id_prefix = "td:"`
- `TEST_PLAN_LABELS = {}`

Cleanup now deletes by client-id prefix for supported entities and still uses the older name/reference prefixes as fallback where `client_id` is not available.

Cleanup is idempotent.

---

## Transaction Boundary Limitation

This system does not wrap the full payload in one global transaction.

Reason:

- some underlying live services commit internally
- some use their own `db.session.begin()` blocks
- some only flush

Consequence:

- earlier entities may remain committed if a later entity fails
- callers should pair creation with cleanup in test teardown when repeatability matters

---

## Guidance for Developers and AI Agents

- Do not reintroduce config-based defaults into this package.
- Add new entity types by updating:
  - `processors/`
  - `ref_map.py`
  - `creator.py`
  - unit tests under `tests/unit/services/commands/test_data/`
- If a service requires `{"fields": [...]}`, keep that wrapping inside the processor, not in the caller contract.
- Keep payload customization in JSON, not in function signatures.
- Preserve the distinction between symbolic refs in payload and actual DB ids used by services.
