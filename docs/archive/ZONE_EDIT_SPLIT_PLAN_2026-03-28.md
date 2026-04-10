# Zone Edit Split — Backend Implementation Plan

Created: 2026-03-28
Status: Ready for implementation
Scope: Backend only — split `update_zone` into two commands with independent guards

Read before starting:
- `Delivery_app_BK/routers/api_v2/zones.py` — current router
- `Delivery_app_BK/services/commands/zones/update_zone.py` — current command (being replaced)
- `Delivery_app_BK/services/commands/zones/create_zone_template.py` — template upsert (unchanged, reference for pattern)
- `Delivery_app_BK/zones/services/postgis_geometry.py` — geometry derivative refresh (used in geometry command)

---

## Context

The current `update_zone` command handles name and geometry under a single blanket guard:
`version.is_active → raise ValidationFailed`. This is too restrictive.

- **Name** is metadata. Safe to edit on active zones. No operational impact.
- **Geometry** changes which orders get assigned to the zone going forward. Must remain restricted
  to inactive versions to prevent silent drift on live delivery days.
- **Template config** already has its own endpoint (`PUT /template`) with no active-version guard.
  It is correct as-is. Do not touch it.

---

## What Changes

| Current | After |
|---|---|
| `services/commands/zones/update_zone.py` | Renamed to `update_zone_geometry.py` — spatial fields only, active-version guard kept |
| _(nothing)_ | New `services/commands/zones/update_zone_name.py` — name only, no active-version guard |
| `PATCH /<version_id>/zones/<zone_id>` | Now calls `update_zone_name` — name only |
| _(nothing)_ | New `PATCH /<version_id>/zones/<zone_id>/geometry` — calls `update_zone_geometry` |

---

## FILE 1 — Rename and trim: `update_zone.py` → `update_zone_geometry.py`

**File:** `Delivery_app_BK/services/commands/zones/update_zone_geometry.py`

Delete `update_zone.py` and create `update_zone_geometry.py` in its place.

Keep the docstring, the serializer, and the active-version guard. Remove `name` from the allowed fields.

```python
"""Update geometry for a zone — only allowed on zones in an inactive version."""
```

Logic (same as current `update_zone`, minus name handling):
1. Load `Zone` by `zone_id`, verify `zone.team_id == ctx.team_id` — else `NotFound`
2. If `version_id` path param provided: verify `zone.zone_version_id == version_id` — else `NotFound`
3. Load `ZoneVersion` for `zone.zone_version_id`
4. If `version.is_active is True` → raise `ValidationFailed("Cannot edit zone geometry in an active version. Create a new version to redraw zone boundaries.")`
5. Apply only spatial fields present in `ctx.incoming_data`:
   - `geometry` (dict/GeoJSON)
   - `centroid_lat`, `centroid_lng` (floats)
   - `min_lat`, `max_lat`, `min_lng`, `max_lng` (floats)
   - If none of these fields are present in the payload → raise `ValidationFailed("No geometry fields provided.")`
6. If `geometry` was updated: call `db.session.flush()` then `refresh_zone_geometry_derivatives(zone.id)`
7. `db.session.commit()`
8. Return serialized zone (same `_serialize_zone` shape as before)

Allowed fields set: `{"geometry", "centroid_lat", "centroid_lng", "min_lat", "max_lat", "min_lng", "max_lng"}`

The `_serialize_zone` helper can stay in this file since it is shared shape.
If you want to avoid duplication between the two commands, extract it to:
`Delivery_app_BK/services/queries/zones/serialize_zone.py`
and import it in both commands. Prefer the extraction — it avoids drift.

---

## FILE 2 — Create: `update_zone_name.py`

**File:** `Delivery_app_BK/services/commands/zones/update_zone_name.py`

```python
"""Update the name of a zone — allowed on both active and inactive versions."""
```

Logic:
1. Load `Zone` by `zone_id`, verify `zone.team_id == ctx.team_id` — else `NotFound`
2. If `version_id` path param provided: verify `zone.zone_version_id == version_id` — else `NotFound`
3. Extract `name` from `ctx.incoming_data`
   - If absent or empty → raise `ValidationFailed("name must be a non-empty string")`
   - Strip whitespace
4. `zone.name = name.strip()`
5. `db.session.commit()`
6. Return serialized zone (same `_serialize_zone` shape — import from shared serializer)

No version activity check. No spatial field handling. No geometry derivative refresh.

---

## FILE 3 — Update router: `zones.py`

**File:** `Delivery_app_BK/routers/api_v2/zones.py`

### Change existing PATCH endpoint

```python
@zone_bp.route("/<int:version_id>/zones/<int:zone_id>", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN])
def update_zone_name(version_id: int, zone_id: int):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data={**incoming_data, "version_id": version_id, "zone_id": zone_id},
        identity=identity,
    )
    from Delivery_app_BK.services.commands.zones.update_zone_name import (
        update_zone_name as _update_zone_name,
    )
    outcome = run_service(lambda c: _update_zone_name(c), ctx)
    response = Response()
    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)
    return response.build_successful_response(outcome.data, warnings=ctx.warnings)
```

### Add new geometry PATCH endpoint

```python
@zone_bp.route("/<int:version_id>/zones/<int:zone_id>/geometry", methods=["PATCH"])
@jwt_required()
@role_required([ADMIN])
def update_zone_geometry(version_id: int, zone_id: int):
    identity = get_jwt()
    incoming_data = request.get_json(silent=True) or {}
    ctx = ServiceContext(
        incoming_data={**incoming_data, "version_id": version_id, "zone_id": zone_id},
        identity=identity,
    )
    from Delivery_app_BK.services.commands.zones.update_zone_geometry import (
        update_zone_geometry as _update_zone_geometry,
    )
    outcome = run_service(lambda c: _update_zone_geometry(c), ctx)
    response = Response()
    if outcome.error:
        return response.build_unsuccessful_response(outcome.error)
    return response.build_successful_response(outcome.data, warnings=ctx.warnings)
```

Update the module docstring at the top of `zones.py` to reflect the new routes:
```
PATCH /api_v2/zones/<version_id>/zones/<zone_id>           update zone name (active or inactive)
PATCH /api_v2/zones/<version_id>/zones/<zone_id>/geometry  update zone geometry (inactive only)
```

---

## Serializer Extraction (Recommended)

If extracting the shared serializer, create:

**File:** `Delivery_app_BK/services/queries/zones/serialize_zone.py`

```python
from Delivery_app_BK.models import Zone


def serialize_zone(zone: Zone) -> dict:
    return {
        "id": zone.id,
        "team_id": zone.team_id,
        "zone_version_id": zone.zone_version_id,
        "city_key": zone.city_key,
        "name": zone.name,
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
```

Import it in `update_zone_name.py`, `update_zone_geometry.py`, and check if `create_zone.py`
has its own `_serialize_zone` — if yes, replace it with this import too.

---

## Implementation Order

1. Create `serialize_zone.py` (shared serializer)
2. Create `update_zone_geometry.py` (rename + trim current `update_zone.py`, import shared serializer)
3. Delete `update_zone.py`
4. Create `update_zone_name.py`
5. Update `zones.py` router — change existing PATCH, add geometry PATCH
6. Write tests

---

## Testing Requirements

| Test file | What to test |
|---|---|
| `tests/unit/services/commands/zones/test_update_zone_name.py` | Name updates on active version succeed; name updates on inactive version succeed; empty name returns 400; missing name returns 400; zone not found returns 404; cross-team zone returns 404 |
| `tests/unit/services/commands/zones/test_update_zone_geometry.py` | Geometry update on inactive version succeeds; geometry update on active version returns 400 with correct message; no spatial fields in payload returns 400; `refresh_zone_geometry_derivatives` is called when geometry field is present; zone not found returns 404 |

---

## What Does NOT Change

- `PUT /<version_id>/zones/<zone_id>/template` — template upsert, untouched
- `GET /<version_id>/zones/<zone_id>/template` — template fetch, untouched
- `DELETE /<version_id>/zones/<zone_id>` — delete zone, untouched
- `PUT /<version_id>/zones` — create zone, untouched (though consider importing shared serializer if it has its own `_serialize_zone`)
- All other zone version endpoints — untouched
