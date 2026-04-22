# Logistic Inbound Item Placed — Implementation

Created: 2026-04-22
Source plan: `docs/under_development/LOGISTIC_ITEM_PLACED_INBOUND.md`

---

## Summary

Added an authenticated inbound machine endpoint for logistics `item_placed` events.

The endpoint accepts a scanned external order id, item SKU, and location label, resolves the
matching order and items, stamps `item_position` on all matching items, and emits the existing
order edited event so the frontend can refresh item data.

---

## Implemented Behavior

### Endpoint

Route:

```text
POST /api_v2/logistic/events/item-placed
```

Authentication:

- `x-api-key` header
- compared with `LOGISTIC_API_KEY`
- no JWT
- no role decorator

### Request handling

File: `Delivery_app_BK/services/requests/integration_logistic/item_placed_request.py`

Implemented:

- dataclass request parser for the inbound payload
- validation for:
  - request body object shape
  - `event == "item_placed"`
  - required top-level fields
  - required `logisticLocation.location`

### Order and item resolution

File: `Delivery_app_BK/services/commands/integration_logistic/inbound/item_placed.py`

Implemented lookup behavior:

- order lookup by `Order.external_order_id == request.order_id`
- item lookup by:
  - `Item.order_id == order.id`
  - `Item.article_number == request.item_sku`

This reflects the final implemented behavior after runtime validation against real data.

### Item mutation

For every matching item:

- `item.item_position = request.logistic_location.location`

Then:

- `db.session.commit()`

### Frontend/event notification

After commit, the command emits the existing order edited event with:

```python
changed_sections=["items"]
```

This reuses the standard order event channel rather than introducing a new socket/event type.

### Blueprint registration

Files:

- `Delivery_app_BK/routers/api_v2/integration_logistic.py`
- `Delivery_app_BK/routers/api_v2/__init__.py`

Implemented:

- standalone logistic blueprint
- blueprint registration under `/api_v2/logistic`
- no admin scope guard

---

## Config

File: `Delivery_app_BK/config/default.py`

Implemented config:

```python
LOGISTIC_API_KEY = os.environ.get("LOGISTIC_API_KEY")
```

Final implementation does **not** use `LOGISTIC_TEAM_ID`.

Reason:

- the first implementation was simplified to resolve orders directly by `external_order_id`
- item lookup is then scoped through the resolved order id

This is intentionally less strict than team-scoped matching and should be treated as a
pragmatic first version.

---

## Files Added

- `Delivery_app_BK/services/commands/integration_logistic/__init__.py`
- `Delivery_app_BK/services/commands/integration_logistic/auth/__init__.py`
- `Delivery_app_BK/services/commands/integration_logistic/inbound/__init__.py`
- `Delivery_app_BK/services/commands/integration_logistic/auth/verify_api_key.py`
- `Delivery_app_BK/services/commands/integration_logistic/inbound/item_placed.py`
- `Delivery_app_BK/services/requests/integration_logistic/__init__.py`
- `Delivery_app_BK/services/requests/integration_logistic/item_placed_request.py`
- `Delivery_app_BK/routers/api_v2/integration_logistic.py`
- `tests/unit/services/commands/integration_logistic/test_item_placed.py`
- `tests/unit/services/commands/integration_logistic/test_verify_api_key.py`
- `tests/unit/services/requests/test_item_placed_request.py`

---

## Verification

Verified in this environment:

- static compile of the new logistic integration files and tests
- manual curl-path verification against the endpoint
- runtime correction of order lookup semantics from `client_id` to `external_order_id`

Not verified in this environment:

- full pytest execution
- end-to-end socket delivery

Reason:

- project runtime/test dependencies were not fully available in the shell

---

## Known Tradeoff

Current order resolution is intentionally permissive:

- `external_order_id` only
- no tenant/team guard

That matches the current “dirty first implementation” decision, but it is less safe in a
multi-tenant scenario if `external_order_id` is not globally unique.

---

## Outcome

NextMark can now receive inbound logistics placement events and reflect warehouse shelf/location
updates directly on items via `item_position`, using `external_order_id` and `article_number`
as the matching keys.
