# Item Position Field Change — Backend → Frontend Handoff

Created: 2026-04-22
Scope: `item_position` changes from a foreign-key integer to a plain string label across all item-related endpoints
Backend implementation plan: `Back_end/docs/under_development/ITEM_POSITION_FK_TO_STRING_LABEL.md`

---

## What Changed and Why

Items previously held `item_position_id` — an integer foreign key pointing to a row in the
`ItemPosition` table. The frontend had to either resolve that ID against a locally cached list
or make a secondary request to get the position name.

`item_position` is now a plain string field on the item itself. The value is the `name` of the
chosen `ItemPosition` record, stamped directly onto the item at creation or update — the same
pattern used by `properties` (JSONB). The `ItemPosition` table still exists and its endpoints
are unchanged; it is now treated as a reference template the frontend reads to offer valid
choices to the user, not as a relational target.

---

## ItemPosition Reference Endpoint (unchanged)

Use this to populate a position picker in the UI:

```
GET /api_v2/item_position/
```

Each record in the response has the shape:

```json
{
  "id": 3,
  "client_id": "pos-fragile",
  "name": "Fragile",
  "default": false,
  "description": "Handle with care",
  "is_system": false
}
```

When the user selects a position, pass `name` (the string) as `item_position` in the item
payload — **not** the `id`.

---

## Affected Endpoints

### 1. Create Order with Items — `POST /api_v2/order/`

Items are nested inside the order payload under the `items` key.

**Before**
```json
{
  "items": [
    {
      "article_number": "SKU-001",
      "item_position_id": 3
    }
  ]
}
```

**After**
```json
{
  "items": [
    {
      "article_number": "SKU-001",
      "item_position": "Fragile"
    }
  ]
}
```

- `item_position_id` (integer) is **removed** from the allowed item fields — sending it will return a validation error
- `item_position` (string, optional) is the replacement — pass the `name` value from an `ItemPosition` record

---

### 2. Create Item — `POST /api_v2/item/`

**Before**
```json
{
  "fields": [
    {
      "article_number": "SKU-001",
      "order_id": 42,
      "item_position_id": 3
    }
  ]
}
```

**After**
```json
{
  "fields": [
    {
      "article_number": "SKU-001",
      "order_id": 42,
      "item_position": "Fragile"
    }
  ]
}
```

**Response shape — before**
```json
{
  "item": {
    "id": 101,
    "article_number": "SKU-001",
    "item_position_id": 3,
    "order_id": 42,
    ...
  },
  "order_totals": [...],
  "plan_totals": [...]
}
```

**Response shape — after**
```json
{
  "item": {
    "id": 101,
    "article_number": "SKU-001",
    "item_position": "Fragile",
    "order_id": 42,
    ...
  },
  "order_totals": [...],
  "plan_totals": [...]
}
```

---

### 3. Update Item — `PATCH /api_v2/item/`

**Before**
```json
{
  "targets": [
    {
      "target_id": 101,
      "fields": {
        "item_position_id": 5
      }
    }
  ]
}
```

**After**
```json
{
  "targets": [
    {
      "target_id": 101,
      "fields": {
        "item_position": "Standard"
      }
    }
  ]
}
```

The response for this endpoint does not include item fields directly — it returns `order_totals`
and `plan_totals` only. No response shape change here.

---

### 4. Dedicated Position Update — `PATCH /api_v2/item/<item_id>/position/<value>`

This endpoint updates only the position of a single item.

**Before — `position_id` was an integer in the URL path**
```
PATCH /api_v2/item/101/position/3
```

**After — `position_name` is a string in the URL path**
```
PATCH /api_v2/item/101/position/Fragile
```

No request body required. The string segment is URL-encoded automatically by any HTTP client
(e.g. `"On Hold"` becomes `/api_v2/item/101/position/On%20Hold`).

Response is an empty success envelope — no shape change:
```json
{ "data": {}, "warnings": [] }
```

---

### 5. Get / List Items — `GET /api_v2/item/`

Items in all list and get responses previously returned `item_position_id` (integer).
They now return `item_position` (string or null).

**Before**
```json
{
  "id": 101,
  "article_number": "SKU-001",
  "item_position_id": 3,
  "item_state_id": 1,
  "order_id": 42,
  "item_type": "box",
  "reference_number": null,
  "properties": [...],
  "page_link": null,
  "quantity": 2,
  "dimension_depth": null,
  "dimension_height": null,
  "dimension_width": null,
  "weight": null
}
```

**After**
```json
{
  "id": 101,
  "article_number": "SKU-001",
  "item_position": "Fragile",
  "item_state_id": 1,
  "order_id": 42,
  "item_type": "box",
  "reference_number": null,
  "properties": [...],
  "page_link": null,
  "quantity": 2,
  "dimension_depth": null,
  "dimension_height": null,
  "dimension_width": null,
  "weight": null
}
```

Items with no position assigned will return `"item_position": null`.

---

## Summary of Field Changes

| Context | Old field | Old type | New field | New type |
|---|---|---|---|---|
| Item request body (create / update) | `item_position_id` | `integer` | `item_position` | `string \| null` |
| Item response body (all item reads) | `item_position_id` | `integer \| null` | `item_position` | `string \| null` |
| Position update URL path segment | `/<int:position_id>` | integer | `/<string:position_name>` | string |

---

## What Did Not Change

- The `ItemPosition` table and all its CRUD endpoints (`/api_v2/item_position/`) are unchanged
- The `ItemPosition` response shape is unchanged
- All other item fields (`article_number`, `item_state_id`, `properties`, dimensions, etc.) are unchanged
- Auth requirements on all endpoints are unchanged
