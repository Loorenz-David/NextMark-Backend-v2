# Route Plan Integration — Backend Handoff (Backend → Frontend)

Created: 2026-03-27
Scope: Plan creation zone express path, plan serializer additions, route group total accuracy
Backend source plan: `Back_end/docs/under_development/ZONES_ROUTE_PLAN_INTEGRATION_GAPS.md`
Frontend architecture reference: `Front_end/admin-app/docs/implemented/ZONE_ROUTEGROUP_ARCHITECTURE.md`

---

## What This Covers

Three backend changes are in progress. Two require frontend adaptation. One is transparent.

| Change | Breaking | Frontend action required |
|---|---|---|
| 1. Create plan gains optional `zone_ids` — express materialization path | No — additive only | Adapt create plan payload and response handling when sending zones |
| 2. Plan responses gain `route_groups_count` and inline `route_groups` summary | No — additive only | Consume new fields in plan list and plan detail views |
| 3. Route group `total_orders` kept accurate after order changes | No — behavior only | None |

---

## Change 1 — Create Plan: Optional Zone Express Path

### What changes

`POST /api_v2/route-plans/` gains an optional `zone_ids` field.

**Current behavior (unchanged when `zone_ids` is absent):**
- Create plan only, no route groups created
- Response: `{ delivery_plan: RoutePlan }`

**New behavior when `zone_ids` is provided:**
- Create plan + one RouteGroup per zone + one RouteSolution per route group, pre-filled from zone template defaults
- Response: `{ delivery_plan: RoutePlan, route_groups: RouteGroup[] }`

This is an **express path** — equivalent to calling create plan then `POST /route-groups/materialize` in one request. The separate materialize endpoint remains unchanged and is still the way to add zones to an existing plan.

### Request shape

```typescript
// All existing fields remain. zone_ids is new and optional.
interface CreatePlanPayload {
  label: string
  start_date: string           // ISO date
  date_strategy?: string       // "single" | "range"
  end_date?: string
  order_ids?: number[]
  route_group_defaults?: object
  zone_ids?: number[]          // NEW — optional list of active zone IDs for this team
}
```

`zone_ids` rules:
- Must be active zone IDs belonging to the team's current active zone version
- Duplicates are ignored
- Invalid or foreign zone IDs return `410` with the offending IDs listed
- Empty array `[]` is treated the same as absent — no route groups created

### Response shape

When `zone_ids` is absent or empty (current behavior, unchanged):
```json
{
  "data": {
    "created": [
      {
        "delivery_plan": { "id": 1, "label": "...", "route_groups_count": 0, ... }
      }
    ]
  }
}
```

When `zone_ids` is provided:
```json
{
  "data": {
    "created": [
      {
        "delivery_plan": { "id": 1, "label": "...", "route_groups_count": 2, ... },
        "route_groups": [
          {
            "id": 10,
            "name": "Zone North",
            "zone_id": 3,
            "zone_geometry_snapshot": { "type": "Polygon", "coordinates": [] },
            "template_snapshot": { "default_service_time_seconds": 120, ... },
            "total_orders": 0,
            "state": { "id": 1, "name": "open" },
            "client_id": "route_group:1:3",
            "route_plan_id": 1,
            "driver_id": null,
            "actual_start_time": null,
            "actual_end_time": null,
            "updated_at": "2026-03-27T..."
          }
        ]
      }
    ]
  }
}
```

The `route_groups` array shape is identical to the objects returned by `GET /route-plans/<id>/route-groups/`.

### Frontend adaptation

- **Plan creation form with zone selection step**: if the user has selected zones before submitting the form, include `zone_ids` in the create payload. The response will contain `route_groups` — write them to the route group store immediately, same as you would after a successful materialize call.
- **Plan creation form without zones**: no change. Response has no `route_groups` key. Existing path works as-is.
- **Do not call `materialize` after a create that already included `zone_ids`** — the groups are already in the DB and returned in the create response.
- The `route_groups` key is **absent** (not `[]`) when no zones were sent. Guard with `bundle.route_groups ?? []` if iterating.

---

## Change 2 — Plan Responses: `route_groups_count` and Inline Summary

### What changes

All plan responses gain `route_groups_count`. The single-plan detail response additionally gains a lean `route_groups` summary list.

### Plan list response (`GET /api_v2/route-plans/`)

Each plan object now includes:

```typescript
interface RoutePlan {
  // ...existing fields
  route_groups_count: number  // NEW — always present, 0 when no route groups exist
}
```

Use this to render zone count badges on plan cards without a separate request.

### Plan detail response (`GET /api_v2/route-plans/<id>`)

The `route_plan` object now includes both `route_groups_count` and a lean inline summary:

```typescript
interface RoutePlanDetail extends RoutePlan {
  route_groups_count: number  // NEW
  route_groups: RoutePlanRouteGroupSummary[]  // NEW — lean list, not full shape
}

interface RoutePlanRouteGroupSummary {
  id: number
  name: string | null
  zone_id: number | null
  total_orders: number | null
  state: { id: number; name: string } | null
}
```

This summary is intentionally lean — it does not include geometry snapshots, driver, or solution data. Use `GET /route-plans/<id>/route-groups/` when you need the full shape.

### Frontend adaptation

- Add `route_groups_count` to the `RoutePlan` TypeScript type
- Add `route_groups` (as `RoutePlanRouteGroupSummary[]`) to the plan detail type — distinct from the full `RouteGroup` type
- Plan list: use `route_groups_count` to render "N zones" on the plan card
- Plan detail: use the inline `route_groups` summary to render a zone summary panel without an extra fetch. The full `GET /route-plans/<id>/route-groups/` call is still needed when rendering the full route group rail with geometry, driver, and solution data.
- Both fields are always present. `route_groups_count` is `0` and `route_groups` is `[]` for plans with no groups.

---

## Change 3 — Route Group `total_orders` Accuracy (Transparent)

### What changes

`RouteGroup.total_orders` will now be recomputed whenever orders are added, removed, or zone-reassigned. Currently it is only computed once at materialization time and goes stale.

### Frontend adaptation

None. The field and its location in the payload are unchanged. Values will just be more accurate after this ships. No type changes, no key renames.

---

## What Does NOT Change

- Separate materialize endpoint: `POST /api_v2/route-plans/<id>/route-groups/materialize` — unchanged, still the standard path for adding zones to an existing plan
- Route group full shape from the list endpoint — unchanged
- Zone CRUD endpoints — unchanged (already shipped, see `ZONES_ENDPOINT_HANDOFF_2026-03-27_13-07-56.md`)
- Plan state endpoints — unchanged
- Order list per plan (`GET /route-plans/<id>/orders/?route_group_id=<id>`) — unchanged

---

## Global Response Envelope (Reminder)

```json
{
  "data": {},
  "warnings": []
}
```

Error:
```json
{
  "error": "Human readable message",
  "code": "DOMAIN_ERROR_CODE"
}
```

Common status codes: `410` validation, `414` not found, `413` permission denied.

---

## Parallel Work Guidance

The backend is implementing these changes now. Frontend can start adapting in parallel:

1. **Immediately**: Add `route_groups_count` to the `RoutePlan` type and consume it in the plan card — it is a purely additive field, safe to add before backend ships (will just be `undefined` until then, guard with `?? 0`).
2. **After backend ships Change 1**: Add the `zone_ids` express path to `planApi.createPlan` and the plan creation form logic. Update the create response handler to write `route_groups` to the store when present.
3. **After backend ships Change 2**: Add `route_groups` summary type and consume it on the plan detail view.
