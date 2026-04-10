# Zone Template Service Update Plan

> Status: PENDING IMPLEMENTATION
> Scope: Service layer only — request parsing, command, queries, serialization.
> No router changes. No model changes. No migrations.

---

## Problem Statement

The ZoneTemplate model was expanded from a single `config_json` JSONB blob to
typed columns in Phase 4 of the Facility/Vehicle expansion. However, the service
layer was not updated. As of now:

- `create_zone_template.py` still reads `config_json` from the request and writes
  `config_json=config_json` to the model (column no longer exists).
- `get_zone_template.py` still serializes `config_json` (column no longer exists).
- `list_zones_for_version.py` still inlines `config_json` in its template dict.
- The serializer function is copy-pasted across three files with no shared source.
- There is no request schema — field validation is a two-line dict check.

---

## Architectural Decisions

**Request parsing** uses `@dataclass` + a `parse_*_request()` function + private
`_validate_*` helpers. This is the established codebase pattern — do not use
Pydantic here.

**Serializer** is extracted to a single shared function in the queries layer.
Both the command (after write) and the query (on read) import from the same place.
This eliminates the three-way copy-paste divergence.

**Facility existence check** is done inside the command, not the request parser.
The parser validates shape and type. DB existence is a command concern.

**Enum validation** reuses the existing domain enum strings already defined for
VehicleCapability and route_end_strategy — do not redefine them.

---

## Files Affected

| File | Action |
|---|---|
| `services/requests/zones/__init__.py` | Create (empty, package marker) |
| `services/requests/zones/zone_template.py` | Create — request dataclass + parser |
| `services/queries/zones/serialize_zone_template.py` | Create — shared serializer |
| `services/commands/zones/create_zone_template.py` | Update — use request parser + typed columns |
| `services/queries/zones/get_zone_template.py` | Update — use shared serializer, remove local duplicate |
| `services/queries/zones/list_zones_for_version.py` | Update — use shared serializer for inline template |

Router (`routers/api_v2/zones.py`) is not touched. Its delegation is correct.

---

## Step 1 — `services/requests/zones/zone_template.py`

### Purpose
Parse and validate the raw incoming dict for zone template create/upsert.

### Request fields

| Field | Type | Required | Rules |
|---|---|---|---|
| `name` | str | yes | non-empty string |
| `default_facility_id` | int | no | positive integer; existence validated in command |
| `max_orders_per_route` | int | no | >= 1 |
| `max_vehicles` | int | no | >= 1 |
| `operating_window_start` | str | no | HH:MM format |
| `operating_window_end` | str | no | HH:MM format; if both present, end must be after start |
| `eta_tolerance_seconds` | int | no | 0–7200; defaults to 0 |
| `vehicle_capabilities_required` | list[str] | no | list of valid VehicleCapability values; deduplicated |
| `preferred_vehicle_ids` | list[int] | no | list of positive integers |
| `default_route_end_strategy` | str | no | one of: round_trip, custom_end_address, last_stop |
| `meta` | dict | no | any JSON object |

### Dataclass

```python
@dataclass
class ZoneTemplateRequest:
    name: str
    default_facility_id: int | None
    max_orders_per_route: int | None
    max_vehicles: int | None
    operating_window_start: str | None
    operating_window_end: str | None
    eta_tolerance_seconds: int
    vehicle_capabilities_required: list[str] | None
    preferred_vehicle_ids: list[int] | None
    default_route_end_strategy: str
    meta: dict | None
```

### Parser function signature

```python
def parse_zone_template_request(raw: dict) -> ZoneTemplateRequest:
    ...
```

### Validation helpers (private, defined in this file)

```python
def _validate_hhmm(value, *, field: str) -> str | None:
    """Accept "HH:MM" strings only. Returns None if value is None."""

def _validate_window(start: str | None, end: str | None) -> None:
    """If both are set, end must be strictly after start."""

def _validate_capabilities(value, *, field: str) -> list[str] | None:
    """Validate each item is a known VehicleCapability string. Deduplicate."""

def _validate_route_end_strategy(value, *, field: str) -> str:
    """Validate against {round_trip, custom_end_address, last_stop}."""

def _validate_positive_int(value, *, field: str) -> int | None:
    """Accept int >= 1. Returns None if value is None."""

def _validate_list_of_positive_ints(value, *, field: str) -> list[int] | None:
    """Accept list where each item is a positive integer."""
```

### VehicleCapability and route_end_strategy source

Import the allowed values from the existing domain enums — do not hardcode strings
in this file. Check:
- `services/domain/vehicle/capabilities.py` for VehicleCapability values
- `route_optimization/constants/route_end_strategy.py` for end strategy constants

---

## Step 2 — `services/queries/zones/serialize_zone_template.py`

### Purpose
Single source of truth for converting a ZoneTemplate ORM object to a dict.
Imported by: command (after write), get query, list query.

### Output shape

```python
{
    "id": int,
    "team_id": int,
    "zone_id": int,
    "name": str,
    "version": int,
    "is_active": bool,
    "default_facility_id": int | None,
    "max_orders_per_route": int | None,
    "max_vehicles": int | None,
    "operating_window_start": str | None,    # "HH:MM"
    "operating_window_end": str | None,      # "HH:MM"
    "eta_tolerance_seconds": int,
    "vehicle_capabilities_required": list[str] | None,
    "preferred_vehicle_ids": list[int] | None,
    "default_route_end_strategy": str,
    "meta": dict | None,
    "created_at": str | None,               # isoformat
    "updated_at": str | None,               # isoformat
}
```

### Function signature

```python
def serialize_zone_template(template: ZoneTemplate) -> dict:
    ...
```

No other logic in this file. Pure mapping from ORM to dict.

---

## Step 3 — `services/commands/zones/create_zone_template.py`

### Changes

1. Remove the local `_serialize_zone_template` function entirely.
2. Import `parse_zone_template_request` from the new request file.
3. Import `serialize_zone_template` from the new serializer file.
4. Replace raw dict access with the parsed request object.
5. Add facility existence check: if `req.default_facility_id` is not None, load
   `Facility` by id scoped to `ctx.team_id`. Raise `NotFound` if missing.
6. Pass all typed columns when constructing the `ZoneTemplate` instance.

### New construction block (replacing old config_json block)

```python
req = parse_zone_template_request(ctx.incoming_data)

# Facility existence check
if req.default_facility_id is not None:
    facility = db.session.get(Facility, req.default_facility_id)
    if facility is None or facility.team_id != ctx.team_id:
        raise NotFound(f"Facility {req.default_facility_id} not found")

created = ZoneTemplate(
    team_id=ctx.team_id,
    zone_id=zone_id,
    name=req.name,
    version=next_version,
    is_active=True,
    default_facility_id=req.default_facility_id,
    max_orders_per_route=req.max_orders_per_route,
    max_vehicles=req.max_vehicles,
    operating_window_start=req.operating_window_start,
    operating_window_end=req.operating_window_end,
    eta_tolerance_seconds=req.eta_tolerance_seconds,
    vehicle_capabilities_required=req.vehicle_capabilities_required,
    preferred_vehicle_ids=req.preferred_vehicle_ids,
    default_route_end_strategy=req.default_route_end_strategy,
    meta=req.meta,
)
```

### Return

```python
return serialize_zone_template(created)
```

### What stays the same

- Zone existence + team ownership check
- version_id validation against zone.zone_version_id
- Deactivation of current active templates
- Auto-increment of version number
- `db.session.add` + `db.session.commit` pattern

---

## Step 4 — `services/queries/zones/get_zone_template.py`

### Changes

1. Remove the local `_serialize_zone_template` function.
2. Import `serialize_zone_template` from the new serializer.
3. Replace the return line with `serialize_zone_template(template)`.

No logic changes. The query itself is correct.

---

## Step 5 — `services/queries/zones/list_zones_for_version.py`

### Changes

1. Import `serialize_zone_template` from the new serializer.
2. Replace the inline template dict construction in the `for template in active_templates` loop:

```python
# Before
templates_by_zone_id[template.zone_id] = {
    "id": template.id,
    "zone_id": template.zone_id,
    "name": template.name,
    "config_json": template.config_json,
    "version": template.version,
    "is_active": template.is_active,
}

# After
templates_by_zone_id[template.zone_id] = serialize_zone_template(template)
```

No other changes to this file.

---

## Verification Checklist

- [ ] `grep -r "config_json" services/` returns zero hits in zone-related files
- [ ] `_serialize_zone_template` function no longer exists in any zone service file
- [ ] `PUT /<version_id>/zones/<zone_id>/template` accepts all new typed fields and rejects unknown ones
- [ ] `GET /<version_id>/zones/<zone_id>/template` returns all typed fields in response
- [ ] `GET /<version_id>/zones` returns typed template fields in each zone's `template` key
- [ ] Invalid `default_facility_id` returns 404
- [ ] Invalid `operating_window_end` before `operating_window_start` returns 400
- [ ] Invalid `vehicle_capabilities_required` value returns 400
- [ ] Invalid `default_route_end_strategy` value returns 400
- [ ] `eta_tolerance_seconds` outside 0–7200 returns 400
- [ ] All fields optional except `name`; omitting any non-required field results in `null` on those columns
- [ ] Existing tests pass: `tests/unit --ignore=tests/unit/ai`

---

## Implementation Order

```
Step 1 (request schema)
    ↓
Step 2 (shared serializer)
    ↓
Step 3 (command)    Step 4 (get query)    Step 5 (list query)
                    ↑ both import Step 2 — independent of each other
```

Steps 3, 4, and 5 can be done in any order after Steps 1 and 2 are in place.
