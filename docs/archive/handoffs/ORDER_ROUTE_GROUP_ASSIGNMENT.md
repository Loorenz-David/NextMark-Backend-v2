# Order Route Group Assignment Architecture

## Overview

This document describes how the backend manages order routing through **route plans** and **route groups**, including creation, plan changes, and group reassignments. Understand these contracts to ensure frontend requests align with backend validation rules.

---

## Core Concepts

### Order Ownership vs. Assignment Context

Orders have **two distinct routing relationships**:

| Field | Meaning | Ownership | Nullable | When Set |
|-------|---------|-----------|----------|----------|
| `route_plan_id` | Which delivery plan owns the order | **Yes** | Can be NULL (unassigned) | Creation or explicit assignment |
| `route_group_id` | Which group within the plan executes the order | **No** (when plan assigned) | Must be set if `route_plan_id` is set | Creation or group reassignment |

**Key Rule**: If an order has a `route_plan_id`, it **MUST** also have a valid `route_group_id` that belongs to that plan.

---

## 1. Order Creation with Initial Route Group

### How It Works

When creating an order and assigning it to a plan immediately, you must provide both `route_plan_id` and `route_group_id`.

```
Order Created
    ↓
Requires: route_plan_id (mandatory if assigning to plan)
Requires: route_group_id (mandatory if route_plan_id is provided)
    ↓
Validate: route_group_id belongs to route_plan_id
    ↓
✓ Order stored with both relationships
```

### API Contract

**Endpoint**: `POST /orders`

**Request Payload**:
```json
{
  "external_id": "ORD-12345",
  "route_plan_id": 42,
  "route_group_id": 5,
  "order_notes": "Handle with care",
  "items": [
    {
      "sku": "SKU-001",
      "quantity": 2
    }
  ],
  "delivery_window": {
    "start_time": "2026-03-28T09:00:00Z",
    "end_time": "2026-03-28T17:00:00Z"
  }
}
```

**Validation Rules**:
- ✅ If `route_plan_id` is provided, `route_group_id` **must** be provided
- ✅ `route_group_id` must exist and belong to the specified `route_plan_id`
- ✅ Both must belong to the same team as the authenticated user
- ✅ `order_notes` is optional (stored on order for reference)

**Success Response** (201):
```json
{
  "id": 500,
  "route_plan_id": 42,
  "route_group_id": 5,
  "state": "pending_assignment",
  "order_stops": [],
  "default_route_stops": []
}
```

**Error Response** (422):
```json
{
  "error": "route_group_id must be provided when route_plan_id is specified",
  "code": "validation_failed"
}
```

### Backend Process

```python
# Services: Delivery_app_BK/services/commands/order/create_order.py
create_order(
    route_plan_id=42,
    route_group_id=5,  # ← REQUIRED if route_plan_id is set
    order_notes="...",
    ...
)
```

**Internal Flow**:
1. Parse `route_group_id` from payload
2. Enforce `route_group_id` is required when `route_plan_id` is present
3. Load route group and validate it belongs to plan + team
4. Create order with **both** relationships persisted
5. No plan-change context needed (new order, no old plan)
6. Return created order with empty `order_stops[]` (not yet assigned to routes)

---

## 2. Order Movement Between Route Plans

### How It Works

An order changes ownership from one plan to another. The destination plan may have **multiple groups**, so the system needs to know which group should execute the order in the new plan.

```
Order in Plan A, Group 1
    ↓
Request Move to Plan B
    ↓
Destination route_group_id needed?
    ├─ Explicit: Frontend provides destination_route_group_id
    ├─ Inference (fallback): 
    │   ├─ Plan B has 1 group only? → Auto-select it
    │   └─ Plan B has multiple groups? → Check order's zone assignment
    │       └─ Map zone to Plan B's zone-group mappings
    │           └─ Found unambiguous mapping? → Use it
    │           └─ Ambiguous or not found? → ERROR
    ↓
✓ Order moved to Plan B, new group selected
✓ Old stops removed from Plan A
✓ New stops created in Plan B, Group X
```

### API Contract

**Endpoint**: `PATCH /orders/<order_id>/plan/<plan_id>`

**Request Payload** (minimal - system infers group):
```json
{
  "prevent_event_bus": false
}
```

**Request Payload** (explicit group):
```json
{
  "route_group_id": 7,
  "prevent_event_bus": false
}
```

**Validation Rules**:
- ✅ `plan_id` must exist and belong to the order's team
- ✅ `route_group_id` (if provided) must belong to `plan_id`
- ✅ If not provided, system attempts inference:
  - If destination plan has only 1 group → use it
  - If multiple groups → lookup order's `OrderZoneAssignment`:
    - Map zone to `RouteGroup.zone_id` in destination plan
    - If unique match → use it
    - If ambiguous or no match → **raise ValidationFailed**

**Success Response** (200):
```json
{
  "updated": [
    {
      "order": {
        "id": 500,
        "route_plan_id": 99,
        "route_group_id": 7,
        "state": "routed_confirmed",
        "order_stops": [
          {
            "id": 1001,
            "stop_order": 1,
            "route_solution_id": 501
          }
        ]
      },
      "route_solution": [
        {
          "id": 501,
          "route_group_id": 7,
          "updated_at": "2026-03-28T10:30:00Z"
        }
      ],
      "order_stops": [
        {
          "id": 1001,
          "stop_order": 1
        }
      ],
      "plan_totals": [
        {
          "id": 42,
          "total_weight": 500,
          "total_items": 2,
          "total_orders": 10
        },
        {
          "id": 99,
          "total_weight": 1500,
          "total_items": 5,
          "total_orders": 25
        }
      ]
    }
  ],
  "pending_events": [
    {
      "type": "order_route_plan_changed",
      "order_id": 500,
      "old_plan_id": 42,
      "new_plan_id": 99
    }
  ]
}
```

**Error Response** (422) - Ambiguous destination group:
```json
{
  "error": "Unable to infer destination route_group_id for order 500.",
  "code": "validation_failed"
}
```

**Solution**: Frontend must provide explicit `route_group_id` in request.

### Backend Process

```python
# Services: Delivery_app_BK/services/commands/order/update_order_route_plan.py
apply_orders_route_plan_change(
    order_ids=[500],
    plan_id=99,
    destination_route_group_id=7,  # ← Optional; system infers if omitted
)
```

**Internal Flow**:

1. **Load old/new route plans** and lock target orders for update

2. **Resolve destination route group** with three strategies:
   ```
   if destination_route_group_id provided:
       validate_belongs_to_plan(destination_route_group_id, plan_id)
   
   elif len(route_groups_for_new_plan) == 1:
       use single_group
   
   else:
       # Multi-group plan: infer from zone
       zone_assignment = OrderZoneAssignment.get(order_id)
       mapped_group = route_group_id_by_zone[zone_assignment.zone_id]
       if not mapped_group:
           raise ValidationFailed("Cannot infer group from zone")
   ```

3. **Build plan-change context** (loads all groups, routes, solutions for old/new plans)

4. **Apply route-plan move handler**:
  - Remove order stops from old group's routes
  - Create order stops in destination group's routes
  - Sync affected route metadata (vehicle positions, stop orders)

5. **Recompute plan/group totals** (weight, volume, item count, order count)

6. **Apply state transitions** (order state, plan state, auto-complete if all orders assigned)

7. **Emit events**:
   - `order_route_plan_changed` → Frontend, WebSocket, Analytics

---

## 3. Order Movement Between Route Groups (Same Plan)

### How It Works

An order stays in the same plan but switches to a different execution group. This is useful for load balancing, skill-based routing, or vehicle reassignments.

```
Order in Plan A, Group 1
    ↓
Request Move to Plan A, Group 2
    ↓
Validation:
    ├─ New group belongs to same plan? ✓
    ├─ Old/new groups are different? ✓
    ├─ Plan has multiple groups? ✓
    ↓
✓ Remove stops from Group 1 routes
✓ Create stops in Group 2 routes
✓ Recompute both groups' metrics
```

### API Contract

**Endpoint**: `PATCH /orders/<order_id>/plan/<plan_id>`

**Request Payload**:
```json
{
  "route_group_id": 3,
  "prevent_event_bus": false
}
```

**Validation Rules**:
- ✅ `plan_id` must be the order's **current** `route_plan_id`
- ✅ `route_group_id` must belong to `plan_id`
- ✅ `route_group_id` must be **different** from order's current group
- ✅ If not provided → system infers (same as cross-plan, but within same plan)

**Success Response** (200):
```json
{
  "updated": [
    {
      "order": {
        "id": 500,
        "route_plan_id": 42,
        "route_group_id": 3,
        "state": "routed_confirmed",
        "order_stops": [
          {
            "id": 2001,
            "stop_order": 5,
            "route_solution_id": 502
          }
        ]
      },
      "route_solution": [
        {
          "id": 501,
          "route_group_id": 1,
          "stops_count": 9  // Old group: 1 stop removed
        },
        {
          "id": 502,
          "route_group_id": 3,
          "stops_count": 11  // New group: 1 stop added
        }
      ],
      "order_stops": [
        {
          "id": 2001,
          "stop_order": 5
        }
      ],
      "plan_totals": [
        {
          "id": 42,
          "total_orders": 25
        }
      ]
    }
  ]
}
```

### Backend Process

```python
# Same endpoint, same function
apply_orders_route_plan_change(
    order_ids=[500],
    plan_id=42,  # ← Same plan as current!
    destination_route_group_id=3,
)
```

**Internal Flow**:

1. Detect same-plan move (old_plan_id == new_plan_id)

2. Load both old and new route groups from context

3. For route-plan move execution:
   - Remove stops from old group's route solutions
   - Create stops in new group's route solutions
   - Sync both groups' routes

4. Recompute metrics for **both groups** (they're in same plan, but have separate totals)

5. Plan-level totals **do not change** (order stays in plan)

6. Emit events:
   - `order_route_plan_changed` (with old_group_id, new_group_id in extended payload)

---

## 4. Batch Order Movement

### API Contract

**Endpoint**: `PATCH /plans/<plan_id>/batch`

**Request Payload**:
```json
{
  "orders": {
    "selection": "all",          // or "by_ids", "by_filters", "by_expression"
    "filters": [...],
    "order_ids": [500, 501, 502]
  },
  "route_group_id": 7,           // Optional; same inference as single
  "prevent_event_bus": false
}
```

**Validation**:
- ✅ Each order in selection is loaded and locked
- ✅ Destination route group validated for each order
- ✅ If not provided, inferred per-order (may fail if ambiguous for any order)

**Success Response** (200):
```json
{
  "signature": "sha256:abc123...",
  "resolved_count": 3,
  "updated_count": 3,
  "updated_bundles": [
    { /* order 500 bundle */ },
    { /* order 501 bundle */ },
    { /* order 502 bundle */ }
  ]
}
```

---

## Error Scenarios & Handling

### Scenario 1: Missing Route Group on Create

**Frontend Request**:
```json
{
  "route_plan_id": 42
  // Missing route_group_id
}
```

**Backend Response** (422):
```json
{
  "error": "route_group_id must be provided when route_plan_id is specified",
  "code": "validation_failed"
}
```

**Frontend Fix**: Add `route_group_id` to payload.

---

### Scenario 2: Invalid Route Group Ownership

**Frontend Request**:
```json
{
  "route_plan_id": 42,
  "route_group_id": 999  // Belongs to a different plan
}
```

**Backend Response** (422):
```json
{
  "error": "route_group_id must belong to the route plan",
  "code": "validation_failed"
}
```

**Frontend Fix**: Query plan's route groups first, ensure group_id belongs to plan_id.

---

### Scenario 3: Cross-Plan Move with Multiple Destination Groups, Ambiguous Zone

**Frontend Request**:
```json
{
  "plan_id": 99
  // No route_group_id provided
  // Order's zone cannot be mapped to plan 99's groups
}
```

**Backend Response** (422):
```json
{
  "error": "Unable to infer destination route_group_id for order 500.",
  "code": "validation_failed"
}
```

**Frontend Options**:
1. Show user a modal to select destination group from `GET /plans/{plan_id}/route_groups`
2. Re-submit with explicit `route_group_id`

---

## Data Model Relationships

### Order Model
```python
class Order(db.Model):
    id: int                      # Unique identifier
    route_plan_id: int | None    # FK to RoutePlan (ownership)
    route_group_id: int | None   # FK to RouteGroup (execution context)
    order_state_id: int          # Current state (pending, routed, delivered, etc.)
```

### RouteGroup Model
```python
class RouteGroup(db.Model):
    id: int
    route_plan_id: int           # FK to RoutePlan (parent)
    zone_id: int | None          # Optional: maps to OrderZoneAssignment.zone_id
    team_id: int                 # Ownership
    orders: List[Order]          # Relationship: groups can have many orders
```

### RoutePlan Model
```python
class RoutePlan(db.Model):
    id: int
    team_id: int
    route_groups: List[RouteGroup]  # 1:N relationship
    total_orders: int            # Denormalized count
```

---

## Frontend Checklist

When implementing order creation/movement on the frontend:

- [ ] **On Create**: If setting `route_plan_id`, always include `route_group_id`
- [ ] **On Plan Change**: 
  - [ ] Show route group selector if destination plan has multiple groups
  - [ ] Attempt inference if only 1 group exists or if system can infer from zone
  - [ ] Handle `validation_failed` errors by prompting user to select
- [ ] **On Group Change**: Ensure plan_id stays the same; only group_id changes
- [ ] **Batch Operations**: 
  - [ ] For cross-plan moves with multiple groups, require explicit selection per order or show multi-select modal
  - [ ] Handle batch errors gracefully (one order fails doesn't fail the whole batch)
- [ ] **Display**: Show current route group alongside route plan in order detail view
- [ ] **Validation**: Before submit, call `GET /plans/{plan_id}/route_groups` to populate dropdowns

---

## Summary Table

| Operation | Old Plan | New Plan | Require route_group_id? | Inference Available? |
|-----------|----------|----------|------------------------|----------------------|
| Create order | — | Specified | **YES** | No (new order) |
| Move between plans | Different | Different | NO* | YES (if unambiguous) |
| Move between groups | Same | Same | NO* | YES (if needed) |
| Batch move | Various | Same | NO* | YES (per-order) |

*= Can omit if system can infer or if destination has only 1 group.

---

## Questions?

Refer to move orchestration logic in:
- `Delivery_app_BK/services/commands/order/update_order_route_plan.py` → cross-plan moves
- `Delivery_app_BK/services/commands/order/plan_changes/` → route-plan change orchestration
- `Delivery_app_BK/services/commands/order/create_order.py` → creation validation
