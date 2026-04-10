# Facility, Vehicle and Zone Config Expansion - Implementation Summary

Status: IMPLEMENTED
Date: 2026-03-29
Scope: Model layer and schema migrations

## Summary

The planned schema refactor for facility, vehicle, zone template, and route solution was implemented and migrated successfully.

All five planned phases were completed:

1. Rename warehouse to facility
2. Expand facility model with typed operational columns
3. Expand vehicle model with facility anchoring and capability/state columns
4. Replace zone template config_json blob with typed columns
5. Add facility foreign keys to route solution

## Delivered Changes

### Phase 1 - Warehouse to Facility rename

- Table rename: warehouse -> facility
- Model rename: Warehouse -> Facility
- File rename and API/service/query rename from warehouse to facility
- Router endpoints updated from /warehouses/ to /facilities/

### Phase 2 - Facility model expansion

Added columns:

- facility_type (default: "warehouse")
- can_dispatch (default: false)
- can_receive_returns (default: false)
- operating_hours (JSONB)
- default_loading_time_seconds (default: 600)
- default_unloading_time_seconds (default: 300)
- max_orders_per_day
- external_refs (JSONB)

Added indexes:

- ix_facility_facility_type on (team_id, facility_type)
- ix_facility_can_dispatch on (team_id, can_dispatch)

### Phase 3 - Vehicle model expansion

Added columns:

- home_facility_id -> facility.id (nullable, ondelete SET NULL)
- status (default: "idle")
- is_active (default: true)
- capabilities (JSONB)
- loading_time_per_stop_seconds (default: 0)
- unloading_time_per_stop_seconds (default: 0)
- fixed_cost (default: 0)

Added relationship:

- Vehicle.home_facility

Added indexes:

- ix_vehicle_home_facility_id on (team_id, home_facility_id)
- ix_vehicle_is_active on (team_id, is_active)
- ix_vehicle_status on (team_id, status)

### Phase 4 - ZoneTemplate typed config

Removed:

- config_json

Added typed columns:

- default_facility_id -> facility.id (nullable, ondelete SET NULL)
- max_orders_per_route
- max_vehicles
- operating_window_start
- operating_window_end
- eta_tolerance_seconds (default: 0)
- vehicle_capabilities_required (JSONB)
- preferred_vehicle_ids (JSONB)
- default_route_end_strategy (default: "round_trip")
- meta (JSONB)

Added relationship:

- ZoneTemplate.default_facility

Added index:

- ix_zone_template_default_facility on (team_id, default_facility_id)

### Phase 5 - RouteSolution facility anchors

Added columns:

- start_facility_id -> facility.id (nullable, ondelete SET NULL)
- end_facility_id -> facility.id (nullable, ondelete SET NULL)

Added relationships:

- RouteSolution.start_facility
- RouteSolution.end_facility

Added index:

- ix_route_solution_start_facility_id on (start_facility_id)

## Migration Chain

Applied migrations:

1. a2b3c4d5e6f7_rename_warehouse_to_facility.py
2. b3c4d5e6f7a2_expand_facility_model.py
3. c4d5e6f7a2b3_expand_vehicle_model.py
4. d5e6f7a2b3c4_expand_zone_template.py
5. e6f7a2b3c4d5_add_facility_fks_to_route_solution.py

## Verification

- Migration execution: successful
- Import smoke checks: successful
- Unit tests: 321 passed, 0 failed (tests/unit --ignore=tests/unit/ai)

## Post-Implementation Additions (same date)

After the initial migration/model rollout, domain standardization and validation hardening were added.

### 1. Facility domain validation standardization

Added centralized facility domain validators and enums under services/domain:

- services/domain/facility/facility_types.py
- services/domain/facility/operating_hours.py

Added model-level SQLAlchemy validates in Facility model for:

- facility_type
- operating_hours

Behavior:

- facility_type is normalized to canonical lowercase and validated against allowed values
- operating_hours is validated for shape, allowed weekdays, HH:MM format, duplicates, and open/close ordering

### 2. Vehicle domain validation standardization

Added centralized vehicle domain validators and enums under services/domain:

- services/domain/vehicle/fuel_type.py
- services/domain/vehicle/travel_mode.py
- services/domain/vehicle/status.py
- services/domain/vehicle/capabilities.py

Added model-level SQLAlchemy validates in Vehicle model for:

- fuel_type
- travel_mode
- status
- capabilities

Behavior:

- fuel_type normalized to lowercase and validated
- travel_mode normalized to uppercase and validated
- status normalized to lowercase and validated
- capabilities validated as list of allowed strings, normalized and deduplicated

### 3. Shared import normalization

Vehicle request parsing and route optimization travel mode mapping now import validators/mappers from services/domain/vehicle so there is one source of truth across app layers.

### 4. Cleanup for schema clarity

Removed non-DB enum helper classes that could imply table-backed integer enums:

- FacilityTypeId
- FuelTypeId
- TravelModeId
- VehicleStatusId
- VehicleCapabilityId

This keeps naming aligned with the actual schema, which stores enum-like values as strings.

## Notes

- RouteSolution start anchor resolution behavior remains domain-layer logic:
  - if start_facility_id is present, use facility coordinates
  - otherwise fall back to start_location JSONB
- This behavior was documented and preserved as planned.
