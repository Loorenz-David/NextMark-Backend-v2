# Test Data Post-Implementation Review Fixes

**Date:** 2026-03-31
**Status:** Implemented
**Archived review plan:** `docs/archive/TEST_DATA_POST_IMPLEMENTATION_REVIEW_2026-03-31.md`
**Scope:** `Delivery_app_BK/services/commands/test_data/`

---

## Summary

This follow-up pass closed the concrete issues identified in the post-implementation review of the JSON-driven test-data system.

The fixes were intentionally small and targeted:

- removed one dead configuration entry
- added one defensive processor default to prevent a runtime DB failure
- added fast failure for unknown top-level payload keys
- updated internal documentation for required fields and transaction behavior

---

## Implemented Fixes

### 1. Removed dead `route_solution` ref-map entry

File:

- `Delivery_app_BK/services/commands/test_data/ref_map.py`

Change:

- deleted the unused `route_solution` block from `REF_FIELD_MAP`

Reason:

- `route_solution` is not part of `PROCESSING_ORDER`
- no `route_solution` processor exists
- leaving the entry in place implied unsupported behavior

### 2. Defaulted `ItemProperty.required` to `False`

File:

- `Delivery_app_BK/services/commands/test_data/processors/item_property.py`

Change:

- added `fields.setdefault("required", False)`

Reason:

- `ItemProperty.required` is non-nullable at the model level
- omitting it from payloads previously caused an integrity failure during flush

### 3. Rejected unknown top-level payload keys

File:

- `Delivery_app_BK/services/commands/test_data/creator.py`

Change:

- added validation before dispatch:
  - allows known entity keys
  - allows `_meta`
  - rejects everything else with `ValueError`

Reason:

- previously unknown keys were silently ignored
- that made typos and unsupported entity attempts hard to diagnose

### 4. Updated architecture and usage documentation

File:

- `Delivery_app_BK/services/commands/test_data/TEST_DATA_CONTEXT.md`

Documentation added or corrected:

- unknown top-level key rejection
- `item_property.required` example/default
- required `items[].article_number`
- global transaction limitation across the full payload

---

## Test Updates

Updated tests:

- `tests/unit/services/commands/test_data/processors/test_item_property.py`
- `tests/unit/services/commands/test_data/test_creator.py`

Coverage added:

- item-property defaulting of `required`
- rejection of unknown top-level entity keys

---

## Verification

Command:

```bash
.venv/bin/python -m pytest tests/unit/services/commands/test_data -q
```

Result:

```text
47 passed in 0.90s
```

---

## Result

The review findings that required implementation are resolved. The remaining documented limitation is transactional: some underlying services commit independently, so the overall test-data payload is not atomic and cleanup remains the recovery path for partial runs.
