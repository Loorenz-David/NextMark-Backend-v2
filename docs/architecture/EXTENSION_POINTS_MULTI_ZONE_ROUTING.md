# Extension Points: Multi-Route by Zone Support

**Version**: 1.0  
**Date**: 2026-03-25  
**Status**: Draft - Prepared but not yet implemented  
**Scope**: Route plans with zone-aware route selection

## Overview

This document outlines the extension points and architectural patterns that will enable zone-aware multi-route selection in route plans. The refactored bounded context structure (Phase 1-5) created the foundation; this phase prepares the service layer for zone-scoped route decisions.

---

## Current State (Post-Phase-5)

### Order Assignment Workflow
```
Order Created (unassigned)
    ↓
Order Assigned to Plan
    ↓
Route Solution Created (single route)
    ↓
Driver Selects Route (picks best option)
```

### Limitations
- ❌ No zone-based routing constraints
- ❌ Single route per plan (assumes all stops in one route)
- ❌ No way to route orders to different zones
- ❌ Order-to-zone affinity not considered

---

## Future State (Post-Phase-6)

### Order Assignment Workflow with Zone Awareness
```
Order Created (unassigned)
    ↓
Order Assigned to Plan + Zone
    ↓
Zone Router Evaluates Applicable Routes
    ↓
Multi-Route Solutions Generated (one per zone)
    ↓
Driver Selects Best Route by Zone
```

### Improvements
- ✅ Zone-based multi-route selection
- ✅ Order-to-zone affinity constraint
- ✅ Cross-zone optimization (if supported)
- ✅ Load balancing by zone

---

## Extension Points

### 1. Route Selection Service

**Location**: `/services/commands/route_operations/select_route_by_zone.py` (new)

**Current Implementation**:
```python
# services/commands/plan/local_delivery/route_solution/select_route_solution.py
def select_route_solution(
    ctx: ServiceContext,
    order_id: int,
    route_solution_id: int,
) -> RouteSolution:
    """Select single route (no zone awareness)"""
```

**Extension Point**:
```python
def select_routes_by_zone(
    ctx: ServiceContext,
    order_id: int,
    route_by_zone: dict[int, int],  # zone_id → route_id
) -> list[RouteSolution]:
    """Select one route per zone (future enhancement)
    
    Inputs:
    - order_id: Order to route
    - route_by_zone: Zone-to-route mapping
    
    Outputs:
    - List of selected route solutions (one per zone)
    
    Constraints:
    - Order can belong to only one zone
    - Each zone can have one selected route
    - Route must be in order's zone
    """
```

### 2. Zone Assignment Service

**Location**: `/services/commands/order_assignment/assign_order_to_zone.py` (new)

**Extension Point**:
```python
def assign_order_to_plan_and_zone(
    ctx: ServiceContext,
    order_id: int,
    plan_id: int,
    zone_id: int | None = None,
) -> Order:
    """Assign order to plan + optional zone
    
    If zone_id provided:
    - Order is scoped to that zone
    - Only routes in that zone are valid
    - Order cannot be moved across zones
    
    If zone_id is None:
    - Order uses plan default zone
    - Full plan scope available (old behavior)
    """
```

### 3. Route Solution Generator

**Location**: `/services/commands/plan/local_delivery/route_solution/generate_multi_zone_solutions.py` (new)

**Extension Point**:
```python
def generate_route_solutions_by_zone(
    ctx: ServiceContext,
    route_plan_id: int,
    zone_ids: list[int] | None = None,
) -> dict[int, RouteSolution]:
    """Generate route solutions scoped by zone
    
    For each zone:
    - Create independent RouteSolution
    - Include only zone-relevant orders
    - Run optimization per zone
    - Return zone → solution mapping
    
    Constraints:
    - Zones must be in plan's zone list
    - Orders must be pre-assigned to zones
    - Optimization per-zone (no cross-zone)
    """
```

### 4. Zone Router Decision Logic

**Location**: `/services/commands/plan/local_delivery/zone_routing/router.py` (new)

**Extension Point**:
```python
class ZoneRoutingDecision:
    """Decision from zone router about route assignments"""
    zone_id: int
    route_solution_id: int
    confidence: float  # 0.0-1.0 (certainty of assignment)
    reason: str  # Why this zone→route mapping


def route_orders_by_zone(
    ctx: ServiceContext,
    route_plan_id: int,
    pending_orders: list[Order],
) -> dict[int, list[ZoneRoutingDecision]]:
    """Route pending orders to zones + routes
    
    Decision Logic (to be customized):
    1. Check order affinity (preferred zone)
    2. Load-balance by zone capacity
    3. Minimize cross-zone transfers
    4. Consider zone operating hours
    
    Returns:
    - order_id → list of ZoneRoutingDecisions
    - Sorted by confidence (best first)
    """
```

---

## Service Composition Pattern

### Before (Single Route)
```
Order Assignment
    ↓
create_route_solution_stops()  ← Creates single route
    ↓
build_route_solution_stops()   ← Applies optimization
    ↓
Select Route
    ↓
Complete Plan State Transition
```

### After (Multi-Route by Zone)
```
Order Assignment (with zone)
    ↓
route_orders_by_zone()         ← Decide zones + routes
    ↓
[For each zone]:
    create_route_solution_stops(zone_id)
        ↓
    build_route_solution_stops(zone_id)
        ↓
[After all zones]:
    select_routes_by_zone(zone_route_mapping)
    ↓
Complete Plan State Transition
```

### Integration Pattern
```python
# In local_delivery_app/apply_order_objective.py (or future variant)

def apply_order_objective_with_zones(
    ctx: ServiceContext,
    order_instance,
    route_plan,
    plan_objective: str,
) -> PlanObjectiveCreateResult:
    """Enhanced objective handler supporting zones"""
    
    route_group = _get_route_group(ctx, route_plan.id)
    
    # NEW: Get zone assignments for all orders
    zone_assignments = _get_zone_assignments(ctx, route_plan.id)
    
    # NEW: Build routes per zone
    route_solutions_by_zone = {}
    for zone_id in zone_assignments.values():
        route_solutions_by_zone[zone_id] = (
            generate_route_solutions_by_zone(
                ctx, route_plan.id, [zone_id]
            )
        )
    
    # Rest of logic remains similar,
    # but operates per-zone instead of globally
    
    return result
```

---

## Schema Extensions (Future)

### Order Table
```sql
ALTER TABLE orders ADD COLUMN zone_assignment_id INT;
-- Links to desired delivery zone
-- Must match plan's zone_list if specified

ALTER TABLE orders ADD COLUMN zone_affinity VARCHAR(50);
-- "preferred", "hard_constraint", "flexible"
-- Determines how strictly zone must be respected
```

### RoutePlan Table
```sql
ALTER TABLE delivery_plans ADD COLUMN zone_routing_mode VARCHAR(50);
-- "none" (current), "soft", "hard", "optimized"
-- Controls how zone constraints are enforced

ALTER TABLE delivery_plans ADD COLUMN zone_ids JSONB;
-- ["zone-1", "zone-2", ...] 
-- Defines valid zones for this plan
```

### RouteSolution Table
```sql
ALTER TABLE route_solutions ADD COLUMN zone_id INT;
-- Which zone this route serves
-- NULL = whole plan (backwards compat)

ALTER TABLE route_solutions ADD COLUMN is_multi_zone_solution BOOL DEFAULT FALSE;
-- True if generated as part of multi-zone set
```

---

## Testing Strategy

### Unit Tests
```python
# services/commands/plan/local_delivery/zone_routing/test_zone_router.py
def test_zone_router_assigns_orders_to_appropriate_zones()
def test_zone_router_respects_capacity_constraints()
def test_zone_router_handles_affinity_preferences()
```

### Integration Tests
```python
# tests/integration/zone_routing/test_multi_zone_route_plan.py
def test_create_plan_with_zones_and_assign_orders()
def test_zone_aware_route_optimization()
def test_driver_selects_routes_within_zones()
def test_unassign_removes_order_from_zone()
```

### Scenario Tests
```
Scenario 1: Hard Zone Constraint
  - Order assigned with zone=north
  - Only north-zone routes available
  - Cannot be moved to south zone
  - ✅ Driver sees only north routes

Scenario 2: Soft Zone Preference
  - Order assigned with zone_affinity="preferred"
  - North zone near capacity
  - Algorithm suggests south zone
  - ✅ Driver can accept suggestion or override

Scenario 3: Load Balancing
  - 10 orders, 2 zones
  - Each order has no affinity
  - Router balances: 5 per zone
  - ✅ Even distribution by demand

Scenario 4: Zone Transition
  - Order initially south zone
  - Changed to north zone
  - Route stops must be recreated
  - Previous south routes updated
  - ✅ Transitions seamlessly
```

---

## Implementation Roadmap

### Phase 6.1: Infrastructure (Ready Now)
- ✅ Extension point definitions (this document)
- ✅ Service composition patterns defined
- ✅ Database migration patterns outlined
- Ready for implementation sprint

### Phase 6.2: Zone Assignment Service (Next Sprint)
- [ ] Create zone models + tables
- [ ] Implement assign_order_to_zone service
- [ ] Update Order Assignment API to accept zone_id
- [ ] Integration tests for zone assignment

### Phase 6.3: Multi-Route Generation (Following Sprint)
- [ ] Implement generate_route_solutions_by_zone
- [ ] Update route creation to be zone-scoped
- [ ] Build zone router logic
- [ ] Optimization per-zone

### Phase 6.4: Driver Experience (Sprint 4)
- [ ] Update select_route_solution to handle zones
- [ ] Driver UI shows zone-filtered routes
- [ ] Allow cross-zone selection (with validation)
- [ ] Zone-aware stop timing

---

## Backward Compatibility

### Without Zones (Default)
```python
# Old code still works
assign_order_to_plan(plan_id, order_id)  # No zone_id

# New code with zones
assign_order_to_plan_and_zone(plan_id, order_id, zone_id=None)
```

- If `zone_id=None`, behaves like current single-route system
- All zones treated as one logical zone
- No breaking changes to existing flows

### Migration Path
1. Deploy Phase 6.1 infrastructure (no-breaking changes)
2. Run Phase 6.2-6.4 in separate sprints (optional adoption)
3. Existing orders continue working with zone_id=NULL
4. New orders can optionally specify zones

---

## Success Criteria

### Functional
- ✅ Orders can be assigned to specific zones
- ✅ Multi-route solutions generated per zone
- ✅ Drivers see zone-scoped routes only
- ✅ Orders cannot move across zones (with constraints)
- ✅ Load balanced across zones

### Non-Functional
- ✅ No performance regression for non-zone deliveries
- ✅ Zone routing < 500ms per 100 zones
- ✅ Multi-zone optimization 95th percentile < 2s
- ✅ Zone assignments queryable in < 100ms

### Observability
- ✅ Zone assignment success/failure tracked
- ✅ Zone-to-route routing latency monitored
- ✅ Load distribution across zones visible
- ✅ Zone constraint violations logged

---

## References

### Related Documentation
- API Migration Guide: `/API_MIGRATION_GUIDE.md`
- Architecture: `/docs/architecture/REALTIME_SYSTEM_ARCHITECTURE.md`
- Data Models: `/docs/domain/models.md`

### Design Patterns Used
- Service composition (separate zone concerns)
- Strategy pattern (zone routing decisions)
- Adapter pattern (optional zone support)
- Extension methods (route solution generation)

### Team Context
- Delivery Platform Team
- Planner UI Development
- Driver App Development Zone-Aware Features Roadmap
