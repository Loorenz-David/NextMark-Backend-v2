# API V2 Route Architecture Migration Map

This document maps the previous API v2 delivery-plan endpoints to the new
route-plan architecture endpoints.

## Route Plans

| Previous path | New path |
|---|---|
| `GET /api_v2/plans/` | `GET /api_v2/route_plans/` |
| `GET /api_v2/plans/states/` | `GET /api_v2/route_plans/states/` |
| `POST /api_v2/plans/` | `POST /api_v2/route_plans/` |
| `PATCH /api_v2/plans/` | `PATCH /api_v2/route_plans/` |
| `DELETE /api_v2/plans/` | `DELETE /api_v2/route_plans/` |
| `GET /api_v2/plans/:planId` | `GET /api_v2/route_plans/:routePlanId` |
| `GET /api_v2/plans/:planId/orders/` | `GET /api_v2/route_plans/:routePlanId/orders/` |
| `PATCH /api_v2/plans/:planId/state/:stateId` | `PATCH /api_v2/route_plans/:routePlanId/state/:stateId` |
| `PATCH /api_v2/plans/:planId/plan-is-ready` | `PATCH /api_v2/route_plans/:routePlanId/ready` |

## Route Groups

| Previous path | New path |
|---|---|
| `PATCH /api_v2/local_delivery_plans/settings` | `PATCH /api_v2/route_groups/settings` |
| `GET /api_v2/local_delivery_plans/plans/:planId` | `GET /api_v2/route_groups/route_plans/:routePlanId` |

## Route Plan Overviews

| Previous path | New path |
|---|---|
| `GET /api_v2/plan_overviews/:planId/local_delivery/` | `GET /api_v2/route_plan_overviews/:routePlanId/route_group/` |

## Route Operations

These endpoints already matched the new architecture and remain unchanged.

Base prefix:

- ` /api_v2/route_operations `

Examples:

- `PATCH /api_v2/route_operations/route-stops/:routeStopId/position/:position`
- `PATCH /api_v2/route_operations/route-stops/group-position`
- `PATCH /api_v2/route_operations/route-stops/:routeStopId/service-time`
- `PATCH /api_v2/route_operations/route-stops/:routeStopId/actual-arrival-time`
- `PATCH /api_v2/route_operations/route-stops/:routeStopId/actual-departure-time`
- `PATCH /api_v2/route_operations/routes/:routeSolutionId/select`
- `PATCH /api_v2/route_operations/routes/:routeSolutionId/actual-start-time`
- `PATCH /api_v2/route_operations/routes/:routeSolutionId/actual-end-time`
- `GET /api_v2/route_operations/routes/:routeSolutionId`
- `POST /api_v2/route_operations/optimize`
- `PATCH /api_v2/route_operations/optimize`

## New Canonical Endpoint Added

This endpoint is new in the route-plan architecture and does not have a legacy
equivalent.

- `GET /api_v2/route_plans/:routePlanId/route_groups/`

Current status:

- Router scaffold exists
- Service integration is pending
- Temporary response shape:

```json
{
  "data": {
    "route_plan_id": 123,
    "route_group": []
  },
  "warnings": [
    "Route plan route groups endpoint scaffolded; service integration pending."
  ]
}
```
