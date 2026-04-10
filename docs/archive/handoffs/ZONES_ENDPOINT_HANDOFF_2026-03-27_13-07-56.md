# Zones and Route Groups API Handoff (Backend -> Frontend)

Created at: 2026-03-27 13:07:56 CET
Scope: Endpoint contract handoff for update/delete corrections and route-group path normalization
Owner: Backend

## Purpose
This document provides frontend-ready API contracts for newly implemented correction endpoints and the finalized route-group URL conventions.

## Global Response Envelope

### Success
HTTP 200

```json
{
  "data": {},
  "warnings": []
}
```

### Error

```json
{
  "error": "Human readable message",
  "code": "DOMAIN_ERROR_CODE"
}
```

Common statuses:
- 410: validation error
- 414: not found
- 413: permission denied
- 510: generic domain error

---

## 1) Update Zone

- Method: PATCH
- Path: /api_v2/zones/{version_id}/zones/{zone_id}
- Roles: ADMIN
- Request body: partial updates supported

### Request Body (all fields optional)

```json
{
  "name": "Zone North",
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[18.01, 59.30], [18.12, 59.30], [18.12, 59.36], [18.01, 59.36], [18.01, 59.30]]]
  },
  "centroid_lat": 59.3293,
  "centroid_lng": 18.0686,
  "min_lat": 59.30,
  "max_lat": 59.36,
  "min_lng": 18.01,
  "max_lng": 18.12
}
```

### Success data payload

```json
{
  "id": 7,
  "team_id": 1,
  "zone_version_id": 12,
  "city_key": "stockholm",
  "name": "Zone North",
  "zone_type": "user",
  "centroid_lat": 59.3293,
  "centroid_lng": 18.0686,
  "geometry": { "type": "Polygon", "coordinates": [] },
  "min_lat": 59.3,
  "max_lat": 59.36,
  "min_lng": 18.01,
  "max_lng": 18.12,
  "is_active": true,
  "template": null,
  "created_at": "2026-03-27T12:00:00+00:00"
}
```

### Validation behavior
- Only zones in inactive versions are editable.
- Zone must belong to both team and version_id path parameter.
- If provided, name must be a non-empty string.

---

## 2) Delete Zone

- Method: DELETE
- Path: /api_v2/zones/{version_id}/zones/{zone_id}
- Roles: ADMIN
- Request body: none

### Success data payload

```json
{
  "deleted": true,
  "zone_id": 7
}
```

### Validation behavior
- Only zones in inactive versions are deletable.
- Deletion is blocked if route groups derived from this zone exist.

---

## 3) Delete Route Group

- Method: DELETE
- Path: /api_v2/route_plans/{route_plan_id}/route-groups/{route_group_id}
- Roles: ADMIN, ASSISTANT
- Request body: none

### Success data payload

```json
{
  "deleted": true,
  "route_group_id": 91
}
```

### Validation behavior
- route_group_id must belong to route_plan_id.
- Deletion is blocked if selected route solution has actual_start_time set.

---

## Route Group URL Convention (Final)

Under route plans, route-group routes are kebab-case:

- GET /api_v2/route_plans/{route_plan_id}/route-groups/
- POST /api_v2/route_plans/{route_plan_id}/route-groups/materialize
- DELETE /api_v2/route_plans/{route_plan_id}/route-groups/{route_group_id}

Note: frontend integrations should stop using underscore path variants for route-group subpaths.

---

## Additional Shape Consistency

Create zone response includes template key for shape parity with list endpoint.

- Endpoint: PUT /api_v2/zones/{version_id}/zones
- Response data now includes:

```json
{
  "template": null
}
```

This avoids frontend normalizer divergence between create and list responses.

---

## Implementation Status

This handoff reflects implemented backend behavior and passing backend unit validation after corrections.
