# Zone Edit Split - Implementation Summary

Created: 2026-03-28
Status: Implemented and validated
Scope: Backend refactor to split zone name updates and geometry updates with independent guards

## Outcome

The zone update flow has been split into two dedicated commands and endpoints:

- Name updates are now metadata-only and allowed for both active and inactive versions.
- Geometry updates are now spatial-only and blocked for active versions.
- Template behavior remains unchanged.

This matches the intended operational model and removes the previous over-restrictive blanket guard.

## Implemented Changes

### 1. Command split

Removed combined command:
- [Delivery_app_BK/services/commands/zones/update_zone.py](Delivery_app_BK/services/commands/zones/update_zone.py)

Added name-only command:
- [Delivery_app_BK/services/commands/zones/update_zone_name.py](Delivery_app_BK/services/commands/zones/update_zone_name.py)

Behavior:
- Validates zone ownership and optional version path match
- Validates name is non-empty string and trims whitespace
- No active-version check
- Commits and returns serialized zone

Added geometry-only command:
- [Delivery_app_BK/services/commands/zones/update_zone_geometry.py](Delivery_app_BK/services/commands/zones/update_zone_geometry.py)

Behavior:
- Validates zone ownership and optional version path match
- Validates zone version ownership
- Blocks active versions with explicit geometry-specific error message
- Accepts only geometry/spatial fields
- Raises error when no spatial fields are provided
- Flushes + refreshes geometry derivatives when geometry is provided
- Commits and returns serialized zone

### 2. Shared serializer extraction

Added shared serializer:
- [Delivery_app_BK/services/queries/zones/serialize_zone.py](Delivery_app_BK/services/queries/zones/serialize_zone.py)

Wired create command to shared serializer:
- [Delivery_app_BK/services/commands/zones/create_zone.py](Delivery_app_BK/services/commands/zones/create_zone.py)

### 3. Router updates

Updated zones router:
- [Delivery_app_BK/routers/api_v2/zones.py](Delivery_app_BK/routers/api_v2/zones.py)

Route mapping now:
- PATCH /api_v2/zones/<version_id>/zones/<zone_id> -> update zone name
- PATCH /api_v2/zones/<version_id>/zones/<zone_id>/geometry -> update zone geometry

Top-level route docstring was updated to include both endpoints.

### 4. Test suite updates

Removed old combined tests:
- [tests/unit/services/commands/zones/test_update_zone.py](tests/unit/services/commands/zones/test_update_zone.py)

Added name command tests:
- [tests/unit/services/commands/zones/test_update_zone_name.py](tests/unit/services/commands/zones/test_update_zone_name.py)

Coverage includes:
- Active version name update succeeds
- Inactive version name update succeeds
- Empty/missing name validation errors
- NotFound and cross-team behavior

Added geometry command tests:
- [tests/unit/services/commands/zones/test_update_zone_geometry.py](tests/unit/services/commands/zones/test_update_zone_geometry.py)

Coverage includes:
- Geometry update on inactive version succeeds
- Geometry update on active version fails with expected message
- No spatial fields fails
- Geometry derivative refresh called when geometry present
- NotFound behavior

## Validation

Executed:
- .venv/bin/python -m pytest tests/unit/services/commands/zones/ -q

Result:
- 18 passed

## Notes

Unchanged behavior by design:
- Zone template endpoints
- Zone deletion flow
- Zone listing and version activation flows

Frontend contract handoff:
- [docs/handoffs_to_front_end/ZONE_EDIT_SPLIT_HANDOFF_2026-03-28.md](docs/handoffs_to_front_end/ZONE_EDIT_SPLIT_HANDOFF_2026-03-28.md)
