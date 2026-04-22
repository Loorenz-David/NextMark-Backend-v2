# Item Position FK to String Label — Implementation

Created: 2026-04-22
Source plan: `docs/under_development/ITEM_POSITION_FK_TO_STRING_LABEL.md`
Frontend handoff: `docs/handoffs_to_front_end/ITEM_POSITION_FIELD_CHANGE_2026-04-22.md`

---

## Summary

`Item.item_position_id` was removed as the stored representation for item position selection and replaced with a plain `item_position` string field on `Item`.

`ItemPosition` remains in place as a team-scoped reference table used to populate frontend choices, but items no longer depend on a foreign-key row at read or write time. The selected label is now stamped directly onto the item record.

This reduces coupling between items and the lookup table, removes FK resolution from create/update flows, and aligns item position behavior with the existing "reference-template plus stamped value" pattern already used elsewhere in the item domain.

---

## Implemented Changes

### 1. Item model

File: `Delivery_app_BK/models/tables/items/item.py`

- Removed `item_position_id` foreign-key column.
- Removed the ORM relationship from `Item` to `ItemPosition`.
- Added `item_position = Column(String, nullable=True, index=True)`.

Result: items now persist the selected position label directly.

### 2. Data migration

File: `migrations/versions/t4u8v2w6x1y5_item_position_fk_to_string.py`

Upgrade behavior:

1. Adds the new `item.item_position` string column.
2. Adds an index for the new column.
3. Backfills existing rows from `item_position.name`.
4. Drops the FK constraint `item_item_position_id_fkey`.
5. Drops the old `item_position_id` column.

Downgrade behavior:

1. Re-adds `item_position_id`.
2. Best-effort backfills IDs by matching `item.item_position` to `item_position.name` within the same team.
3. Recreates the FK constraint.
4. Removes the string column and its index.

Note: the repo currently has two Alembic heads, so this migration was intentionally created with both current heads as `down_revision` to avoid creating an additional migration branch.

### 3. Item create and update command flow

Files:

- `Delivery_app_BK/services/commands/item/create/create_item.py`
- `Delivery_app_BK/services/commands/item/update/update_item.py`
- `Delivery_app_BK/services/commands/order/create_order.py`

Changes:

- Removed `ItemPosition` imports where they were only used for relationship injection.
- Removed `item_position_id` from `relationship_map`.

Result: item creation and update now treat `item_position` as a plain scalar field and no longer resolve or validate an `ItemPosition` FK during persistence.

### 4. Dedicated item-position update route and command

Files:

- `Delivery_app_BK/services/commands/item/update_item_position.py`
- `Delivery_app_BK/routers/api_v2/item.py`

Changes:

- Dedicated command now accepts `position_name: str` instead of `position_id`.
- Route changed from:
  - `PATCH /api_v2/item/<item_id>/position/<int:position_id>`
- To:
  - `PATCH /api_v2/item/<item_id>/position/<string:position_name>`
- Command now writes `item.item_position = position_name`.

Result: the targeted item-position update endpoint now works with labels directly.

### 5. Serialization and query output

Files:

- `Delivery_app_BK/services/commands/order/create_serializers.py`
- `Delivery_app_BK/services/queries/item/serialize_items.py`

Changes:

- Replaced serialized `item_position_id` output with `item_position`.

Result: created item payloads and item list payloads now expose the string label instead of an integer FK.

### 6. Item filtering

File: `Delivery_app_BK/services/queries/item/find_items.py`

Changes:

- Replaced `item_position_id` filtering with `item_position`.
- Removed integer handling for the field and switched filtering to string values.

Result: item search now filters on the stamped string label.

### 7. Request parsing

Files:

- `Delivery_app_BK/services/requests/order/create_order.py`
- `Delivery_app_BK/services/requests/order/update_orders_route_plan_batch.py`

Changes in nested order item parsing:

- Removed `item_position_id` from allowed int item fields.
- Added `item_position` as an optional string field.

Changes in batch selection item filters:

- Replaced allowed filter key `item_position_id` with `item_position`.
- Moved the field from int-filter handling to string-filter handling.

Result: request validation now matches the new API contract.

### 8. Tests added

Files:

- `tests/unit/services/requests/order/test_create_order.py`
- `tests/unit/services/requests/order/test_update_orders_route_plan_batch_request.py`

Added coverage for:

- nested order item payloads accepting `item_position` as a string label
- route-plan batch item filters accepting `item_position` as a string filter

---

## API Contract Impact

Old contract:

- request field: `item_position_id`
- response field: `item_position_id`
- dedicated route path param: integer position ID

New contract:

- request field: `item_position`
- response field: `item_position`
- dedicated route path param: string position label

`ItemPosition` CRUD and lookup endpoints remain unchanged and continue to provide the reference list the frontend should use when offering selectable positions.

---

## What Stayed Unchanged

- `ItemPosition` model and table remain in place.
- `ItemPosition` CRUD routes and query services were not changed.
- Team-scoped reference-template behavior for `ItemPosition` is preserved.

---

## Verification

Verified in this environment:

- static reference sweep for remaining `item_position_id` usages in touched runtime paths
- `python3 -m compileall` on all touched backend files and the migration
- focused request-level test additions

Not verified in this environment:

- runtime execution of the Flask app
- `pytest` test execution
- migration execution against a live database

Reason: the shell environment did not have project runtime dependencies available on PATH, including `pytest` and `flask`.

---

## Outcome

The backend now stores item position as a stable string label on each item while keeping `ItemPosition` as the editable source of selectable options. This removes item-level FK dependency on the lookup table and updates the write paths, read paths, filters, route contract, and migration layer consistently.
