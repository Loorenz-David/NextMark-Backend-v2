# Test Data System — Post-Implementation Review

**Date:** 2026-03-31
**Reviewed against:** `docs/implemented/TEST_DATA_JSON_DRIVEN_REFACTOR_IMPLEMENTATION_2026-03-31.md`
**Implementation location:** `Delivery_app_BK/services/commands/test_data/`

---

## Overall Verdict

The core implementation is correct and clean. The infrastructure layer (`registry.py`, `resolver.py`, `ref_map.py`, `creator.py`) is solid. All 39 tests pass. The findings below are one dead code entry, two undocumented required fields that will produce DB errors at runtime, and one structural observation about transaction isolation. None of these are test data design flaws — they are all fixable with small targeted changes.

---

## Finding 1 — Dead entry in `ref_map.py`: `route_solution`

**Severity: Low — causes confusion, no runtime crash**

**File:** `Delivery_app_BK/services/commands/test_data/ref_map.py`

`REF_FIELD_MAP` contains a `"route_solution"` key with four `$ref` entries:

```python
"route_solution": {
    "$route_group": "route_group_id",
    "$vehicle": "vehicle_id",
    "$start_facility": "start_facility_id",
    "$end_facility": "end_facility_id",
},
```

But `"route_solution"` is **not** in `PROCESSING_ORDER` and has **no processor**. This means:

- If someone passes `"route_solution": [...]` in a payload, the dispatch loop silently skips it (the key is not in `PROCESSING_ORDER`, so the loop never reaches it).
- The `ref_map` entry is dead. A reader of that file reasonably concludes that `route_solution` entities are supported — they are not.
- The resolver would correctly resolve `$ref` keys for `route_solution` items if the dispatcher ever called it, but the dispatcher never does.

**Fix options (pick one):**

**Option A — Remove the dead entry** (simplest):
```python
# Delete the route_solution block from REF_FIELD_MAP
```

**Option B — Add a `route_solution` processor** (adds real value):

`RouteSolution` rows are auto-created by `create_plan` (one per route_group). But occasionally test scenarios need a second variant (a second RouteSolution on an existing RouteGroup). A processor for this would call `create_instance(ctx, RouteSolution, fields)` directly after resolving the refs.

If Option B is chosen, add `"route_solution"` to `PROCESSING_ORDER` between `route_plan` and `order`, and create `processors/route_solution.py`.

**Recommendation: Option A now, Option B when a test scenario actually requires it.**

---

## Finding 2 — `ItemProperty.required` is NOT nullable — will crash if omitted

**Severity: High — produces a DB integrity error at runtime**

**File:** `Delivery_app_BK/models/tables/items/item_property.py`

```python
required = Column(Boolean, nullable=False)
```

`required` has no server-side default and is NOT nullable. If a caller omits it from the payload:

```json
{ "$id": "ip_color", "name": "test-Color", "field_type": "text" }
```

The DB insert will raise an `IntegrityError` (NOT NULL constraint) at flush time. The error message from SQLAlchemy will not clearly point to this field.

**Fix:** Two changes needed.

**1. Document the required field clearly** — add a payload comment in the README or wherever the example payloads live:
```json
{ "$id": "ip_color", "name": "test-Color", "field_type": "text", "required": false }
```

**2. Add a defensive default in the processor** so omitting it doesn't crash:

In `processors/item_property.py`, before calling the service, inject a default:

```python
def process(item: dict, identity: dict, registry: Registry) -> int:
    fields = {key: value for key, value in item.items() if not key.startswith("_")}
    fields.setdefault("required", False)   # ← add this line
    ctx = build_ctx(identity, {"fields": [fields]}, on_create_return="instances")
    result = create_item_property(ctx)
    return result[0].id
```

This is a safe default. `required=False` means the property is optional on orders. A caller who wants required=True still passes it explicitly.

**Add a test:**

```python
# processors/test_item_property.py
def test_process_defaults_required_to_false_if_omitted(monkeypatch):
    calls = []
    def fake_create(ctx):
        calls.append(ctx.incoming_data["fields"][0])
        instance = SimpleNamespace(id=55)
        return [instance]
    monkeypatch.setattr(module, "create_item_property", fake_create)
    module.process({"name": "test-Color", "field_type": "text"}, {"team_id": 5}, None)
    assert calls[0]["required"] is False
```

---

## Finding 3 — `Item.article_number` is required — not surfaced in errors

**Severity: Medium — produces a confusing parse error at runtime**

**File:** `Delivery_app_BK/services/requests/order/create_order.py` → `_parse_item`

```python
"article_number": validate_str(
    item_raw.get("article_number"),
    field=f"items[{index}].article_number",
),
```

`article_number` is required on every inline item. If omitted:

```json
"items": [{ "item_type": "test-Chair", "quantity": 2 }]
```

The order processor will raise `ValidationFailed("items[0].article_number: ...")` from inside `create_order`, which surfaces as an unhandled exception from the `order.py` processor.

This is not a bug in the implementation — the validation is correct. But callers need to know about this constraint. It's not mentioned anywhere in the current system's documentation.

**Fix:** No code change needed. Add to internal documentation / example payloads:

```json
"order": [
  {
    "$route_plan": "p1", "$route_group": "p1.rg.z1",
    "reference_number": "test-001",
    "items": [
      {
        "article_number": "CHAIR-001",   ← required, no default
        "item_type": "test-Vintage Chair",
        "quantity": 2,
        "weight": 12000
      }
    ]
  }
]
```

---

## Finding 4 — No single transaction wrapping all entity creation

**Severity: Informational — existing limitation, not a new bug**

`create_zone_version`, `create_zone`, and `create_zone_template` each call `db.session.commit()` internally. `create_plan` uses `with db.session.begin()`. `create_order` uses `with db.session.begin()`. The `facility.py` and `vehicle.py` processors use `db.session.flush()` without their own `begin()`.

This means if the dispatch loop processes:
1. `facility` → flushed ✓
2. `zone_version` → committed ✓
3. `zone` → committed ✓
4. `route_plan` → committed inside `create_plan`'s `begin()` ✓
5. `order` → **raises ValidationFailed** (e.g., missing `article_number`)

Steps 1–4 are permanently committed. There is no rollback. The partially created data remains in the DB until cleanup is explicitly called.

This is not a bug in the new system — it was the same behaviour in the old orchestrator, which called the same services. The cleanup endpoint exists precisely to handle this.

**Fix:** No code change needed. Document this limitation explicitly in the endpoint's API contract and ensure callers always have a corresponding cleanup call in test teardown.

---

## Finding 5 — `creator.py` silently ignores unknown top-level payload keys

**Severity: Low — silent data loss, not a crash**

If a caller passes a payload key that is not in `PROCESSING_ORDER`:

```json
{ "route_solution": [...], "unknown_entity": [...] }
```

The dispatch loop skips it silently because the loop iterates `PROCESSING_ORDER`, not `payload.keys()`. The caller gets back a result dict with no entry for that key, with no warning or error.

Given that `route_solution` is in `REF_FIELD_MAP` (see Finding 1), a caller might reasonably try to use it and get no result and no error, which is confusing.

**Fix:** After processing, check for unrecognised keys and raise or warn:

```python
# At the top of create_test_data, after the loop:
known_keys = set(PROCESSING_ORDER)
unknown_keys = set(payload.keys()) - known_keys
if unknown_keys:
    raise ValueError(
        f"Unknown entity keys in payload: {sorted(unknown_keys)}. "
        f"Supported keys: {PROCESSING_ORDER}"
    )
```

Place this check **before** the dispatch loop so nothing is created before the error is raised. This makes the failure fast and obvious.

**Add a test:**

```python
# test_creator.py
def test_rejects_unknown_entity_key():
    with pytest.raises(ValueError, match="Unknown entity keys"):
        module.create_test_data({"team_id": 5, "user_id": 1}, {"unknown_entity": [{}]})
```

---

## Summary Table

| # | Finding | Severity | Fix required |
|---|---------|----------|-------------|
| 1 | Dead `route_solution` entry in `ref_map.py` | Low | Remove dead entry from `REF_FIELD_MAP` |
| 2 | `ItemProperty.required` not nullable — crashes if omitted | High | Add `fields.setdefault("required", False)` in `item_property.py` + test |
| 3 | `Item.article_number` required on inline items — not surfaced | Medium | Document in payload examples, no code change |
| 4 | No single transaction across all entities | Informational | Document the limitation, no code change |
| 5 | Unknown payload keys silently skipped | Low | Add unknown-key check before dispatch loop + test |

---

## Implementation Order

1. **Finding 2** (item_property default) — one line + one test. Fixes a runtime crash.
2. **Finding 5** (unknown key check) — one guard + one test. Prevents silent data loss.
3. **Finding 1** (dead ref_map entry) — one deletion. No tests needed.
4. **Finding 3** — documentation only.
5. **Finding 4** — documentation only.
