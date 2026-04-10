# API Migration Guide: Delivery Domains Separation Refactor

**Version**: 2.0  
**Date**: 2026-03-25  
**Status**: Breaking Changes - Clients must migrate to new endpoints

## Executive Summary

This refactor separates monolithic plan/order/route concerns into explicit bounded contexts. All three main operations (order management, plan operations, route runtime) now have dedicated APIs with clearer semantics and improved separation of concerns.

**Key Changes**:
- Order creation no longer auto-assigns to plans (breaking change)
- Order-to-plan assignment moved to dedicated `order_assignments` API
- Route operations moved from generic plan endpoints to dedicated `route_operations` API
- Plan-type-specific operations moved from generic plan endpoints to app-specific APIs
- All changes use break-and-replace strategy; no backward compatibility layer

---

## Endpoint Migration Map

### 1. Order Assignment Operations

#### Create/Update Plan Assignment
| Aspect | Old Endpoint | New Endpoint | Method | Status |
|--------|-------------|--------------|--------|--------|
| **Path** | `PATCH /api_v2/orders/<order_id>/plan/<plan_id>` | `PATCH /api_v2/order_assignments/orders/<order_id>/plan/<plan_id>` | PATCH | **Moved** |
| **Removed Feature** | `delivery_plan_id` in POST `/api_v2/orders` | N/A | N/A | **Breaking** |
| **Purpose** | Assign order to plan + inline side effects | Assign order to plan (explicit) | PATCH | ✅ Maintained |
| **Route Sync** | Automatic | Automatic | PATCH | ✅ Maintained |
| **Plan Totals** | Auto-recomputed | Auto-recomputed | PATCH | ✅ Maintained |
| **Response** | Order + bundle | Order + bundle | PATCH | ✅ Same |

**Migration Action**:
```
Client Code (OLD):
  POST /api_v2/orders { delivery_plan_id: 123, ... }  # BROKEN - field ignored now
  
Client Code (NEW):
  POST /api_v2/orders { ... }  # No plan_id
  PATCH /api_v2/order_assignments/orders/{id}/plan/123
```

#### Unassign Order from Plan
| Aspect | Old | New | Status |
|--------|-----|-----|--------|
| **Feature** | Not available | `PATCH /api_v2/order_assignments/orders/<order_id>/unassign-plan` | ✅ New |
| **Effect** | N/A | Removes route stops, recomputes totals, updates plan state | ✅ New |
| **Response** | N/A | Order + bundle | ✅ New |

**Migration Action**:
```
Client Code (NEW):
  PATCH /api_v2/order_assignments/orders/{id}/unassign-plan
```

#### Batch Assign Orders to Plan
| Aspect | Old | New | Status |
|--------|-----|-----|--------|
| **Endpoint** | `PATCH /api_v2/plans/<plan_id>/batch` | `PATCH /api_v2/order_assignments/plans/<plan_id>/batch` | **Moved** |
| **Purpose** | Batch assign orders | Batch assign orders | ✅ Maintained |
| **Response** | Orders + bundles | Orders + bundles | ✅ Same |

**Migration Action**:
```
Client Code (OLD):
  PATCH /api_v2/plans/123/batch { order_ids: [...] }
  
Client Code (NEW):
  PATCH /api_v2/order_assignments/plans/123/batch { order_ids: [...] }
```

#### Resolve Selection
| Aspect | Old | New | Status |
|--------|-----|-----|--------|
| **Endpoint** | `POST /api_v2/selection/resolve` | `POST /api_v2/order_assignments/selection/resolve` | **Moved** |
| **Purpose** | Resolve batch selection | Resolve batch selection | ✅ Maintained |

---

### 2. Route Operations

#### Select Route Solution
| Aspect | Old | New | Status |
|--------|-----|-----|--------|
| **Endpoint** | `PATCH /api_v2/route_solutions/<route_id>/select` | `PATCH /api_v2/route_operations/routes/<route_id>/select` | **Moved** |
| **Method** | PATCH | PATCH | ✅ Same |
| **Purpose** | Mark route as selected | Mark route as selected | ✅ Same |

**Migration Action**:
```
Client Code (OLD):
  PATCH /api_v2/route_solutions/456/select { selected: true }
  
Client Code (NEW):
  PATCH /api_v2/route_operations/routes/456/select { selected: true }
```

#### Mark Route Timing
| Aspect | Old | New | Status |
|--------|-----|-----|--------|
| **Start Time** | `PATCH /api_v2/route_solutions/<id>/actual-start-time` | `PATCH /api_v2/route_operations/routes/<id>/actual-start-time` | **Moved** |
| **End Time** | `PATCH /api_v2/route_solutions/<id>/actual-end-time` | `PATCH /api_v2/route_operations/routes/<id>/actual-end-time` | **Moved** |

**Migration Action**:
```
Client Code (OLD):
  PATCH /api_v2/route_solutions/456/actual-start-time { timestamp: "2026-03-25T09:00:00Z" }
  
Client Code (NEW):
  PATCH /api_v2/route_operations/routes/456/actual-start-time { timestamp: "2026-03-25T09:00:00Z" }
```

#### Route Stop Operations
| Aspect | Old | New | Status |
|--------|-----|-----|--------|
| **Position** | `PATCH /api_v2/route_stops/<stop_id>/position/<pos>` | `PATCH /api_v2/route_operations/route-stops/<stop_id>/position/<pos>` | **Moved** |
| **Group Position** | `PATCH /api_v2/route_stops/group-position` | `PATCH /api_v2/route_operations/route-stops/group-position` | **Moved** |
| **Service Time** | `PATCH /api_v2/route_stops/<stop_id>/service-time` | `PATCH /api_v2/route_operations/route-stops/<stop_id>/service-time` | **Moved** |
| **Actual Arrival** | `PATCH /api_v2/route_stops/<stop_id>/actual-arrival-time` | `PATCH /api_v2/route_operations/route-stops/<stop_id>/actual-arrival-time` | **Moved** |
| **Actual Departure** | `PATCH /api_v2/route_stops/<stop_id>/actual-departure-time` | `PATCH /api_v2/route_operations/route-stops/<stop_id>/actual-departure-time` | **Moved** |

**Migration Action**:
```
Client Code (OLD):
  PATCH /api_v2/route_stops/789/position/3
  PATCH /api_v2/route_stops/group-position { stops: [...] }
  
Client Code (NEW):
  PATCH /api_v2/route_operations/route-stops/789/position/3
  PATCH /api_v2/route_operations/route-stops/group-position { stops: [...] }
```

#### Get Route Solution
| Aspect | Old | New | Status |
|--------|-----|-----|--------|
| **Endpoint** | `GET /api_v2/route_solutions/<id>` | `GET /api_v2/route_operations/routes/<id>` | **Moved** |
| **Purpose** | Fetch route solution details | Fetch route solution details | ✅ Same |

**Migration Action**:
```
Client Code (OLD):
  GET /api_v2/route_solutions/456
  
Client Code (NEW):
  GET /api_v2/route_operations/routes/456
```

#### Route Optimization
| Aspect | Old | New | Status |
|--------|-----|-----|--------|
| **Optimize** | `POST /api_v2/route_solutions/optimize` | `POST /api_v2/route_operations/optimize` | **Moved** |
| **Update** | `PATCH /api_v2/route_solutions/optimize` | `PATCH /api_v2/route_operations/optimize` | **Moved** |

**Migration Action**:
```
Client Code (OLD):
  POST /api_v2/route_solutions/optimize { plan_id: 123 }
  
Client Code (NEW):
  POST /api_v2/route_operations/optimize { plan_id: 123 }
```

---

### 3. Plan-Type-Specific Operations

#### Local Delivery Settings
| Aspect | Old | New | Status |
|--------|-----|-----|--------|
| **Settings** | `PATCH /api_v2/plans/<plan_id>/local_delivery/settings` | `PATCH /api_v2/local_delivery_plans/settings` | **Moved** |
| **Get Plan Type** | `GET /api_v2/plans/<plan_id>/type` | `GET /api_v2/local_delivery_plans/plans/<plan_id>` | **Moved** |

**Migration Action**:
```
Client Code (OLD):
  PATCH /api_v2/plans/123/local_delivery/settings { max_stops: 45 }
  GET /api_v2/plans/123/type
  
Client Code (NEW):
  PATCH /api_v2/local_delivery_plans/settings { max_stops: 45 }
  GET /api_v2/local_delivery_plans/plans/123
```

#### Store Pickup Plan
| Aspect | Old | New | Status |
|--------|-----|-----|--------|
| **Get Plan Type** | `GET /api_v2/plans/<plan_id>/type` (if store_pickup) | `GET /api_v2/store_pickup_plans/plans/<plan_id>` | **Moved** |

**Migration Action**:
```
Client Code (OLD):
  GET /api_v2/plans/456/type  # Returns { plan_type: "store_pickup" }
  
Client Code (NEW):
  GET /api_v2/store_pickup_plans/plans/456  # Returns store_pickup-specific response
```

#### International Shipping Plan
| Aspect | Old | New | Status |
|--------|-----|-----|--------|
| **Get Plan Type** | `GET /api_v2/plans/<plan_id>/type` (if intl) | `GET /api_v2/international_shipping_plans/plans/<plan_id>` | **Moved** |

**Migration Action**:
```
Client Code (OLD):
  GET /api_v2/plans/789/type  # Returns { plan_type: "international_shipping" }
  
Client Code (NEW):
  GET /api_v2/international_shipping_plans/plans/789  # Returns intl-specific response
```

---

## Breaking Changes Summary

### 1. Order Creation
**Old Behavior**:
```json
POST /api_v2/orders {
  "delivery_plan_id": 123,
  ...
}
```
✅ Order created and assigned to plan in single call

**New Behavior**:
```json
POST /api_v2/orders {
  ...
}
```
❌ `delivery_plan_id` field removed  
❌ Order created **unassigned** (delivery_plan_id = NULL)  
✅ Call `/api_v2/order_assignments/orders/{id}/plan/{plan_id}` separately to assign

**Impact**: Any client passing `delivery_plan_id` must refactor to two-step flow.

### 2. Endpoint Path Changes
All route operations moved from `/api_v2/route_solutions/*` to `/api_v2/route_operations/*`

**Impact**: Route driver app, planner UI, and any client referencing old paths must update.

### 3. Plan-Type Operations
Plan-type-specific endpoints no longer available under generic `/api_v2/plans/<id>`

**Old**:
```
PATCH /api_v2/plans/123/local_delivery/settings
GET /api_v2/plans/123/type
```

**New**:
```
PATCH /api_v2/local_delivery_plans/settings
GET /api_v2/local_delivery_plans/plans/123
```

**Impact**: Plan type-specific clients must migrate to app-specific endpoints.

### 4. Generic Plan Routes
Plan router no longer contains mixed handlers

**What's Removed**:
- `PATCH /api_v2/plans/<id>/local_delivery/*`  
- `GET /api_v2/plans/<id>/type`  
- `GET /api_v2/plans/<id>/type/resolve`

---

## Client Migration Checklist

### For Backend Services
- [ ] Update order creation flow to use two-step assignment
- [ ] Remove `delivery_plan_id` from order creation payloads
- [ ] Update all route operations to use `/api_v2/route_operations/*` paths
- [ ] Update all plan-type queries to use app-specific endpoints
- [ ] Update integration tests with new endpoint paths
- [ ] Validate role-based access (ADMIN/ASSISTANT for assignments, DRIVER for route ops)

### For Frontend Apps
- [ ] **Planner UI**: Update all route solution endpoints to `/api_v2/route_operations/*`
- [ ] **Driver App**: Update all route operation endpoints for timing, stops, optimization
- [ ] **Store Pickup App**: Update plan-type endpoint to `/api_v2/store_pickup_plans/plans/<id>`
- [ ] **International Shipping App**: Update plan-type endpoint to `/api_v2/international_shipping_plans/plans/<id>`
- [ ] **Order Management**: Split order create + assign operations

### For API Clients
- [ ] Search for all `/api_v2/route_solutions/` references
- [ ] Search for all `delivery_plan_id` in order POST payloads
- [ ] Search for all `/api_v2/plans/<id>/type` references
- [ ] Search for all `/api_v2/plans/<id>/local_delivery/` references
- [ ] Update with new endpoint paths

---

## Deployment Strategy

### Phase 1: Preparation (Current)
✅ New endpoints are live and fully functional  
✅ Old endpoints still respond (if not yet removed)  
❌ Clients still using old paths

### Phase 2: Client Migration (Next Sprint)
- Update order assignment flow in backend services
- Update all frontend app endpoints
- Run integration tests
- Deploy frontend updates

### Phase 3: Legacy Endpoint Removal (Post-Migration)
- Monitor old endpoint usage via logs
- Remove deprecated route handlers once all clients migrated
- Archive old handler code for reference

---

## Backward Compatibility

**Status**: None. This is a break-and-replace refactor.

Rationale:  
- Clear separation reduces cognitive load on all clients
- No silent failures or mixed behavior
- Explicit migration targets for all clients
- Easier to maintain long-term

---

## Support & Troubleshooting

### Issue: "delivery_plan_id not accepted in order creation"
**Solution**: Remove `delivery_plan_id` from POST body; use assignment API after creation.

### Issue: "Route operations endpoints return 404"
**Solution**: Update path from `/route_solutions/` to `/route_operations/`.

### Issue: "Plan type endpoint returns unexpected response"
**Solution**: Use app-specific endpoints:
- Local delivery → `/api_v2/local_delivery_plans/plans/<id>`
- Store pickup → `/api_v2/store_pickup_plans/plans/<id>`
- International shipping → `/api_v2/international_shipping_plans/plans/<id>`

### Issue: "Permission denied on order assignments"
**Solution**: Ensure client has ADMIN or ASSISTANT role (DRIVER excluded by design).

---

## Observability & Monitoring

### New Domain Boundaries
Track API usage by domain:
```
/api_v2/order_assignments/     → Order Assignment Boundary
/api_v2/route_operations/      → Route Operations Boundary
/api_v2/local_delivery_plans/  → Local Delivery App
/api_v2/store_pickup_plans/    → Store Pickup App
/api_v2/international_shipping_plans/ → International Shipping App
```

### Key Metrics
- Order creation + assignment latency (now two separate calls)
- Route optimization latency per plan type
- Plan-type-specific operation success rates
- Domain boundary API error rates

---

## Timeline

| Phase | Milestone | Date |
|-------|-----------|------|
| 1 | New endpoints live | 2026-03-25 |
| 2 | Client migration window | 2026-03-25 → 2026-04-08 |
| 3 | Old endpoints decommissioned | 2026-04-09 |
| 4 | Legacy code archived | 2026-04-15 |

**Support Contact**: Delivery Platform Team  
**Questions**: Refer to codebase documentation in `/docs/architecture/`
