# Test Data JSON-Driven Refactor Implementation

**Date:** 2026-03-31
**Status:** Implemented
**Archived plan:** `docs/archive/TEST_DATA_JSON_DRIVEN_REFACTOR_2026-03-31.md`
**Scope:** `Delivery_app_BK/services/commands/test_data/`

---

## Summary

The legacy config-driven test data generator was replaced with a JSON-driven dispatcher centered on:

```python
create_test_data(identity: dict, payload: dict) -> dict
```

The caller now sends a single payload describing what to create. Cross-entity references are expressed with symbolic `$id` / `$ref` keys and resolved during dispatch.

---

## Implemented Structure

The test data package now contains:

- `__init__.py` exporting `create_test_data` and `clear_generated_test_data`
- `creator.py` with the topological dispatch loop
- `registry.py` for symbolic ID registration and reverse lookup
- `ref_map.py` for declarative `$key` to destination-field mapping
- `resolver.py` for pure `$ref` resolution
- `context_builder.py` for processor `ServiceContext` construction
- `cleanup.py` retained, with inline `TEST_PLAN_LABELS = {}`
- `processors/` for entity-specific creation adapters

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

---

## Runtime Changes

- The old orchestrator and config-default flow were removed.
- The seed route in `Delivery_app_BK/routers/api_v2/seed.py` now calls `create_test_data(ctx.identity, ctx.incoming_data)`.
- Dispatch order is fixed internally and does not depend on JSON key order.
- Route plan creation auto-registers synthetic route-group refs:
  - `{plan_sid}.rg.default`
  - `{plan_sid}.rg.{zone_sid}`
- Order items remain denormalized:
  - `item_type` is passed as a string
  - `properties` are passed as inline JSON snapshots

---

## Deleted Legacy Surface

Removed from `services/commands/test_data/`:

- `orchestrator.py`
- `plan_data_creators.py`
- `zone_data_creators.py`
- `facility_data_creators.py`
- `vehicle_data_creators.py`
- `order_data_creators.py`
- `item_types_data_creators.py`
- `item_generator.py`
- `route_solution_settings_updater.py`
- all deleted `config/` defaults modules

Removed legacy unit tests and replaced them with tests for the new dispatcher, resolver, registry, and processors.

---

## Test Coverage

Current replacement unit test suite:

- `tests/unit/services/commands/test_data/test_registry.py`
- `tests/unit/services/commands/test_data/test_resolver.py`
- `tests/unit/services/commands/test_data/test_creator.py`
- `tests/unit/services/commands/test_data/processors/*.py`

Verification run:

```bash
.venv/bin/python -m pytest tests/unit/services/commands/test_data -q
```

Result:

```text
39 passed in 0.59s
```

---

## Review Notes

- The implementation follows the phased structure from the archived plan.
- The test suite verifies the JSON-driven surface and processor wiring, not a full seeded end-to-end DB payload run.
- Cleanup behavior remains prefix/label driven and no longer depends on deleted config defaults.
