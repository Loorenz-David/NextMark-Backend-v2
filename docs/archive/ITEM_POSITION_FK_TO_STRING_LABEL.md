# Item Position — FK to String Label

> **Problem:** `Item` currently holds `item_position_id` as a foreign key to the `ItemPosition`
> lookup table. This couples item records to a specific DB row and requires FK resolution on
> every create/update. The intent is for `ItemPosition` to act like `ItemProperties` — a
> reference template the frontend reads to offer choices, with the selected label stamped
> directly onto the item as a plain string.
>
> **Goal:** Remove the FK column and relationship from `Item`, replace with a plain
> `item_position` string column. Keep the `ItemPosition` table fully intact as a
> team-scoped reference template. Update all commands, serializers, queries, schemas,
> and routes that currently reference `item_position_id`.

---

## Affected Files Overview

| File | Change |
|---|---|
| `models/tables/items/item.py` | Remove FK + relationship, add string column |
| `migrations/versions/<new>_item_position_fk_to_string.py` | Schema + data migration |
| `services/commands/item/create/create_item.py` | Remove FK from `relationship_map` |
| `services/commands/item/update/update_item.py` | Remove FK from `relationship_map` |
| `services/commands/item/update_item_position.py` | Accept string label, not position_id |
| `services/commands/order/create_order.py` | Remove FK from `relationship_map` |
| `services/commands/order/create_serializers.py` | Emit `item_position` string field |
| `services/queries/item/serialize_items.py` | Emit `item_position` string field |
| `services/queries/item/find_items.py` | Filter on string column |
| `services/requests/order/create_order.py` | Move field from int set to string set |
| `services/requests/order/update_orders_route_plan_batch.py` | Move field from int set to string set |
| `routers/api_v2/item.py` | Change position route to accept string path param |

---

## Step-by-Step Implementation

### Step 1 — Model: `Item`
**File:** `Delivery_app_BK/models/tables/items/item.py`

- Remove `item_position_id = Column(Integer, ForeignKey("item_position.id"))`
- Remove `item_position = relationship("ItemPosition", backref="items")`
- Add `item_position = Column(String, nullable=True, index=True)`
- Keep `ForeignKey` import — still used by `order_id` and `item_state_id`

---

### Step 2 — Alembic Migration (new file)
**File:** `migrations/versions/<new_revision_id>_item_position_fk_to_string.py`

Set `down_revision` to the current head revision. Choose a new unique revision ID.

**`upgrade()` — four operations in order:**
1. `op.add_column("item", Column("item_position", String, nullable=True))` — add the new string column
2. Backfill via `op.execute`: `UPDATE item SET item_position = ip.name FROM item_position ip WHERE item.item_position_id = ip.id` — preserve existing position labels as strings
3. `op.drop_constraint("<fk_constraint_name>", "item", type_="foreignkey")` — verify the exact constraint name from `814f1c16cc1a_inital_migration_02_20.py`
4. `op.drop_column("item", "item_position_id")` — remove the old FK column

**`downgrade()` — reverse in order:**
1. `op.add_column("item", Column("item_position_id", Integer, nullable=True))` — restore the int column
2. Reverse backfill: `UPDATE item SET item_position_id = ip.id FROM item_position ip WHERE item.item_position = ip.name AND ip.team_id = item.team_id` — best-effort; rows with unmatched names get NULL
3. `op.create_foreign_key(...)` — restore the FK constraint to `item_position.id`
4. `op.drop_column("item", "item_position")` — remove the string column

---

### Step 3 — Command: `create_item`
**File:** `Delivery_app_BK/services/commands/item/create/create_item.py`

- Remove `ItemPosition` from the model import line
- Remove `"item_position_id": ItemPosition` from `relationship_map`

`item_position` is now a plain string — `inject_fields` will handle it as a simple `setattr`, no FK lookup needed.

---

### Step 4 — Command: `update_item`
**File:** `Delivery_app_BK/services/commands/item/update/update_item.py`

- Remove `ItemPosition` from the model import line
- Remove `"item_position_id": ItemPosition` from `relationship_map`

Same reason as Step 3.

---

### Step 5 — Command: `update_item_position` (dedicated command)
**File:** `Delivery_app_BK/services/commands/item/update_item_position.py`

- Remove `ItemPosition` import
- Remove `get_instance(ctx, ItemPosition, position_id)` call
- Change function signature from `(ctx, item_id, position_id: int)` → `(ctx, item_id, position_name: str)`
- Replace `item_instance.item_position_id = position_instance.id` → `item_instance.item_position = position_name`
- Keep `get_instance(ctx, Item, item_id)`, `db.session.commit()`, and the return unchanged

---

### Step 6 — Command: `create_order` (order-level item creation)
**File:** `Delivery_app_BK/services/commands/order/create_order.py`

- Remove `ItemPosition` from the model import line
- Remove `"item_position_id": ItemPosition` from the `relationship_map` passed to the context

---

### Step 7 — Serializer: `create_serializers`
**File:** `Delivery_app_BK/services/commands/order/create_serializers.py`

- In `serialize_created_items`: replace `"item_position_id": instance.item_position_id` → `"item_position": instance.item_position`

---

### Step 8 — Serializer: `serialize_items`
**File:** `Delivery_app_BK/services/queries/item/serialize_items.py`

- Replace `"item_position_id": instance.item_position_id` → `"item_position": instance.item_position`

---

### Step 9 — Find query: `find_items`
**File:** `Delivery_app_BK/services/queries/item/find_items.py`

- Replace `if "item_position_id" in params:` → `if "item_position" in params:`
- Change filter from `Item.item_position_id.in_(position_ids)` → `Item.item_position.in_(position_names)`
- Rename local variable `position_ids` → `position_names`
- Remove integer coercion — treat values as strings

---

### Step 10 — Request schema: `create_order`
**File:** `Delivery_app_BK/services/requests/order/create_order.py`

- In `ITEM_ALLOWED_FIELDS`: replace `"item_position_id"` → `"item_position"`
- In `ITEM_OPTIONAL_INT_FIELDS`: remove `"item_position_id"`
- In `ITEM_OPTIONAL_STRING_FIELDS`: add `"item_position"`

---

### Step 11 — Request schema: `update_orders_route_plan_batch`
**File:** `Delivery_app_BK/services/requests/order/update_orders_route_plan_batch.py`

- Replace both occurrences of `"item_position_id"` (lines 71 and 89) → `"item_position"`
- Move the field from the int-filter keys set to a string-filter keys set, consistent with how `item_type` is handled in `find_items`

---

### Step 12 — Route: `item.py`
**File:** `Delivery_app_BK/routers/api_v2/item.py`

- Change the route decorator from `/<int:item_id>/position/<int:position_id>` → `/<int:item_id>/position/<string:position_name>`
- Update the function signature to accept `position_name: str` instead of `position_id: int`
- Pass `position_name` (not `position_id`) to the `update_item_position` command call

---

## What Does Not Change

- `ItemPosition` model, table, migrations — untouched
- `ItemPosition` router and all CRUD endpoints — untouched
- `ItemPosition` queries (`find`, `list`, `get`, `serialize`) — untouched
- Bootstrap — `ItemPosition` was never in bootstrap, no change needed

---

## Sequencing Notes

- Steps 1 and 2 are foundational — all other steps depend on the model field being renamed from `item_position_id` (int) to `item_position` (str)
- Steps 3–12 are independent of each other once Steps 1–2 are complete
- Migration in Step 2 must verify the exact FK constraint name from `814f1c16cc1a_inital_migration_02_20.py` before running `op.drop_constraint`
- The backfill in Step 2 is safe to re-run (idempotent for rows with a valid position match)
