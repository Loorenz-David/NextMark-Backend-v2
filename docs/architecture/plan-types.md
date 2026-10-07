# Plan Types

How local delivery, store pickup and international shipping are kept apart so each
can grow without touching the others.

## The rule

> Shared code (orders, plans, realtime) may know that a plan type exists and hand
> work to it. It must never know what a plan type does.

If shared code needs to know about routes, pickups or carriers, it asks the plan
type's module instead. The `route-context` bug that motivated this design came
from breaking that rule: the order realtime emitter attached route freshness to
every order with a plan, so the admin app asked store pickup and international
shipping orders for a route context they can never have.

## Data model

| What | Where |
|---|---|
| Which type a plan is | `RoutePlan.plan_type` — one of `RoutePlan.PLAN_TYPES` |
| Plan-level data for one type | A 1:1 extension table: `StorePickupPlan` (pickup location, assigned user), `InternationalShippingPlan` (carrier) |
| Local delivery's routing data | `RouteGroup` → `RouteSolution` → `RouteSolutionStop` |
| The order's objective | `Order.order_plan_objective`, always set from the plan's type when the order is assigned (the plan owns it) |

Type-specific data never goes on `route_plan` or `order` as nullable columns. When
a type needs order-level fields (pickup window, tracking number, customs status),
add a 1:1 table for that type, e.g. `store_pickup_order` or
`international_shipment_order`.

## Code map

```
services/plan_types/
  contract.py                 PlanTypeModule: the hooks every type implements
  registry.py                 get_plan_type_module(plan_type) -> PlanTypeModule | None
  local_delivery.py           binds local delivery's handlers to the contract
  store_pickup.py             binds store pickup's handlers
  international_shipping.py   binds international shipping's handlers

services/commands/
  local_delivery_app/         local delivery's behaviour (route stops, route sync)
  store_pickup_app/           store pickup's behaviour (no-ops today)
  international_shipping_app/ international shipping's behaviour (no-ops today)
  order/plan_objectives/      shared: resolves the type, calls apply_objective
  order/plan_changes/         shared: resolves both sides, calls apply_plan_change
  order/update_extensions/    shared: groups edited orders by type, calls apply_order_update
  order/delete_extensions/    shared: groups deleted orders by type, calls apply_order_delete

sockets/emitters/order_events.py   shared: merges build_order_realtime_extras into the payload
```

The `*_app/` packages hold behaviour. The `plan_types/` modules only bind that
behaviour to the contract. Shared code imports `get_plan_type_module` and nothing
from any `*_app/` package.

## The hooks

`PlanTypeModule` is a frozen dataclass. Every hook is a required field, so a type
cannot be registered without answering it. A no-op is an explicit choice.

| Hook | Called when | Local delivery | Store pickup / international shipping |
|---|---|---|---|
| `apply_objective` | An order is assigned to a plan of this type | Builds the route stop and queues an incremental route sync | No-op |
| `apply_plan_change` | An order moves between plans | Removes and/or builds stops in one route sync | No-op |
| `apply_order_update` | Orders on this type's plans are edited | Updates stops (address, time window) | No-op |
| `apply_order_delete` | Orders on this type's plans are deleted | Removes stops and re-syncs the route | No-op |
| `build_order_realtime_extras` | An order realtime event is emitted | Adds `route_freshness_updated_at` | Adds nothing |

### Plan changes span two types

`apply_order_plan_change` hands each type only the side that belongs to it:

- **Same type** (local → local): one call with both `old_plan` and `new_plan`.
  Local delivery depends on this to merge the stop removal and creation into a
  single route sync.
- **Cross type** (local → store pickup): the old type gets `(old_plan, None)` and
  tears its artifacts down; the new type gets `(None, new_plan)` and builds its own.

### Realtime and route context

Only local delivery adds `route_freshness_updated_at` to order events. The admin
app's realtime handler (`AdminBusinessRealtimeProvider.tsx`) only fetches
`GET /orders/:id/route-context` when that field is present, so the payload itself
tells the frontend whether a route context exists. The frontend doesn't need to
know the plan type for this.

`route-context` is a local delivery endpoint. For any other order it returns
`not_found`. Error statuses are offset by +10 (not found arrives as **414**,
because CloudFront intercepts 400–405), so the frontend checks
`error.payload?.code === "not_found"`, never the status.

## How to…

### Add behaviour to an existing type

Edit that type's handler in `services/commands/<type>_app/`. Nothing shared
changes. For example, store pickup notifying the assigned user when an order is
assigned goes in `store_pickup_app/apply_order_objective.py`.

### Add a new hook

1. Add a required field to `PlanTypeModule` in `contract.py`, with a comment saying
   when it is called.
2. Implement it in every `*_app/` package (a no-op is fine) and bind it in every
   `plan_types/<type>.py`.
3. Call it from shared code through `get_plan_type_module(plan_type)`, and handle a
   `None` module (an unassigned order has no plan type).

### Add a new plan type

1. Add the value to `RoutePlan.PLAN_TYPES`.
2. Create `services/commands/<type>_app/` with the four command handlers.
3. Create `services/plan_types/<type>.py` binding them, and add it to the tuple in
   `registry.py`.
4. Frontend: add it to `PLAN_TYPES` and the label maps in
   `admin-app/src/features/plan/domain/planType.ts`, and give it a workspace page in
   `features/home-route-operations/registry/planWorkspaceRegistry.ts`. Both are
   keyed by `RoutePlanObjective`, so TypeScript reports every missing entry.

`tests/unit/services/plan_types/test_plan_type_registry.py` fails if a value in
`RoutePlan.PLAN_TYPES` has no registered module.

### Test shared dispatch

Patch `get_plan_type_module` in the orchestrator module under test (see
`tests/unit/services/commands/order/test_plan_change_dispatch.py`).

## Frontend side

| What | Where |
|---|---|
| The list of types, labels, `isLocalDeliveryPlan` | `admin-app/src/features/plan/domain/planType.ts` |
| Which page renders a plan's workspace | `features/home-route-operations/registry/planWorkspaceRegistry.ts` |
| Store pickup UI | `features/store-pickup-orders/`, `features/home-store-pickup/` |
| International shipping UI | `features/international-shipping-orders/`, `features/home-international-shipping/` |
| Local delivery UI | `features/plan/routeGroup/`, `features/home-route-operations/` |

When a type gains its own realtime or order-detail behaviour, add a frontend
plan-type registry alongside `planWorkspaceRegistry` instead of branching on the
type inside shared order code.

## Implementation notes

- **Lazy registry.** `registry.py` imports the type modules on first call. The type
  modules import the order command packages, and those packages import the
  registry, so importing eagerly would create a cycle.
- **Known leaks, not yet moved.** These still live in shared paths and should move
  into `local_delivery_app/` when they are next touched:
  - `order/update_extensions/context_loader.py`, `order/delete_extensions/context_loader.py`
    and `build_plan_change_apply_context` load route groups and solutions for every plan.
  - `order/{update_extensions,delete_extensions,plan_objectives,plan_changes}/local_delivery.py`.
  - Route logic inside generic order commands, mostly `update_order_route_plan.py`.
