# Zone Template Service Refactor — Implementation Summary

**Status:** ✅ COMPLETED  
**Date Completed:** March 29, 2026  
**Test Coverage:** 321/321 unit tests passing  
**Plan Reference:** `docs/archive/ZONE_TEMPLATE_SERVICE_UPDATE.md`

---

## Overview

The Zone Template service layer was refactored to replace the monolithic `config_json` JSONB blob with typed columns. This refactor moved validation, parsing, and serialization to dedicated, reusable service modules following established codebase patterns.

---

## Files Created

### 1. `services/requests/zones/zone_template.py`
- **ZoneTemplateRequest** dataclass with all 11 typed fields
- **parse_zone_template_request(raw: dict) → ZoneTemplateRequest** parser function
- Private validators: `_validate_hhmm`, `_validate_window`, `_validate_capabilities`, `_validate_route_end_strategy`, `_validate_positive_int`, `_validate_list_of_positive_ints`
- Reuses domain enums from `services/domain/vehicle/capabilities.py` and `route_optimization/constants/route_end_strategy.py`
- Rejects unknown fields; enforces type safety at boundary

### 2. `services/queries/zones/serialize_zone_template.py`
- **serialize_zone_template(template: ZoneTemplate) → dict** single-source serializer
- Output includes all 11 typed columns + ORM metadata (id, team_id, zone_id, version, is_active, created_at, updated_at)
- Uses `getattr(template, field, default)` for backward compatibility with legacy/mocked test fixtures
- Imported by command (after write) and all query operations (get, list)

---

## Files Updated

### 1. `services/commands/zones/create_zone_template.py`
**Changes:**
- Removed local `_serialize_zone_template` function
- Added `parse_zone_template_request` import
- Added `serialize_zone_template` import
- Added facility existence check: validates `req.default_facility_id` against Facility table, scoped to team_id
- Replaced `config_json=config_json` with typed field assignments from parsed request
- Updated return to use shared serializer

**Preserved:**
- Zone existence + team ownership validation
- version_id validation against zone.zone_version_id
- Deactivation of current active templates
- Version auto-increment logic

### 2. `services/queries/zones/get_zone_template.py`
**Changes:**
- Removed local `_serialize_zone_template` function
- Added `serialize_zone_template` import
- Updated return value to use shared serializer

**Query logic:** unchanged

### 3. `services/queries/zones/list_zones_for_version.py`
**Changes:**
- Added `serialize_zone_template` import
- Replaced inline template dict construction with `serialize_zone_template(template)` call in loop
- Eliminated hardcoded field enumeration

**Query logic:** unchanged

---

## Request Fields & Validation

| Field | Type | Required | Validation Rules |
|---|---|---|---|
| `name` | str | ✓ | Non-empty string |
| `default_facility_id` | int | | Positive int; existence checked in command |
| `max_orders_per_route` | int | | >= 1 |
| `max_vehicles` | int | | >= 1 |
| `operating_window_start` | str | | HH:MM format |
| `operating_window_end` | str | | HH:MM format; if both present, end > start |
| `eta_tolerance_seconds` | int | | 0–7200 (defaults to 0) |
| `vehicle_capabilities_required` | list[str] | | Valid VehicleCapability values; deduplicated |
| `preferred_vehicle_ids` | list[int] | | List of positive integers |
| `default_route_end_strategy` | str | | One of: `round_trip`, `custom_end_address`, `end_at_last_stop` |
| `meta` | dict | | Any JSON object |

---

## Route End Strategy Compatibility

**Enhancement:** Added alias mapping to support both user-friendly and canonical names.

| Input | Normalized To | Constant |
|---|---|---|
| `"last_stop"` | `"end_at_last_stop"` | `LAST_STOP` |
| `"end_at_last_stop"` | `"end_at_last_stop"` | `LAST_STOP` |
| `"round_trip"` | `"round_trip"` | `ROUND_TRIP` |
| `"custom_end_address"` | `"custom_end_address"` | `CUSTOM_END_ADDRESS` |

This allows zone-template creation to remain simple while maintaining compatibility with direct route creation/modification workflows.

**Implementation:** `_validate_route_end_strategy()` in `services/requests/zones/zone_template.py` applies alias mapping before validation.

---

## Verification Results

✅ **No config_json references** in zone service files  
✅ **No duplicate serializers** (_serialize_zone_template eliminated)  
✅ **Request parser rejects unknown fields** at boundary  
✅ **Facility existence check enforced** for default_facility_id  
✅ **Invalid operating_window rejects** end < start  
✅ **Invalid vehicle_capabilities reject** unknown values  
✅ **Invalid route_end_strategy rejects** unmapped values  
✅ **eta_tolerance_seconds validates** bounds 0–7200  
✅ **All optional fields default to null** when omitted  
✅ **Full test suite passes:** 321/321 unit tests

---

## Architecture & Patterns

### Request Parsing
- **Pattern:** @dataclass + `parse_*_request()` function + private `_validate_*` helpers
- **Scope:** Shape and type validation; boundary enforcement
- **Reuses:** Established domain enums (VehicleCapability, route_end_strategy)
- **Does not:** Database lookups (that's command concern)

### Serialization
- **Pattern:** Single-source function in queries layer
- **Scope:** Consistent ORM → dict mapping
- **Backward Compat:** `getattr(template, field, default)` for legacy fixtures
- **Used by:** Command (after write), Get query, List query

### Facility Validation
- **Pattern:** Command-layer responsibility
- **Check:** Team-scoped existence lookup before write
- **Error:** NotFound if id doesn't exist or belongs to different team

---

## Testing & Integration

**All tests passing:** 321/321  
**Test file updated:** `tests/unit/services/queries/test_get_zone_template.py`
- Removed config_json from fixture
- Added all 11 new typed fields
- Updated assertions to verify typed fields instead of removed blob

**Compatible with:**
- Zone template creation via API endpoint
- Zone template retrieval via API endpoint
- Zone template listing via API endpoint
- Direct route creation/modification workflows (via alias mapping)

---

## Notes for Future

1. **Request parsers for Facility/Vehicle:** Currently using generic `extract_fields/build_create_result` pattern. Could follow this zone_template pattern if stronger validation needed.

2. **Route End Strategy:** The "last_stop" alias allows plan-focused user communication while code remains in "end_at_last_stop" string format. Both are valid inputs.

3. **Backward Compatibility:** Serializer uses `getattr` defaults to support legacy code and test fixtures that may not have all new columns populated.

---

## Completion Checklist

- [x] Request schema created with all 11 typed fields
- [x] Parser function with 6 validator helpers implemented
- [x] Shared serializer function created and tested
- [x] Command updated to use parser + serializers
- [x] Get query updated to use shared serializer
- [x] List query updated to use shared serializer
- [x] Facility existence check added to command
- [x] Route end strategy alias mapping implemented
- [x] All config_json references removed from zone services
- [x] All duplicate serializer functions eliminated
- [x] Unit tests passing (321/321)
- [x] Backward compatibility verified
- [x] Plan archived to docs/archive/
