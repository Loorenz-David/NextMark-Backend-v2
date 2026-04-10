# Zone Management API — Frontend Integration Guide

**Updated:** March 29, 2026  
**Status:** ✅ Ready for Implementation  
**Base URL:** `/api_v2/zones`

---

## Overview

The Zone API is a hierarchical resource system with the following structure:

```
Zone Version (team-level)
  └── Zone (spatial definition, name, geometry)
       └── Zone Template (operational defaults for routing)
```

A **Zone Version** groups related zones and can be activated/deactivated as a unit. Each **Zone** has one active **Zone Template** that defines routing behavior (operating windows, vehicle requirements, facility anchor, etc.).

---

## Authentication & Authorization

All endpoints require:
- **Header:** `Authorization: Bearer <jwt_token>`
- **Role:** Most endpoints require `ADMIN` role
- **Query endpoints** also accept `ASSISTANT` role

Errors:
- `401 Unauthorized` — missing or invalid token
- `403 Forbidden` — insufficient role

---

## Core Endpoints

### 1. Zone Version Management

#### **1.1 List All Zone Versions**

```http
GET /api_v2/zones
```

**Query Parameters:**
- `city_key` (optional) — filter by city; can be any string

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "team_id": 42,
    "city_key": "new_york",
    "name": "NY Zones v1",
    "version": 1,
    "is_active": true,
    "created_by": "admin@company.com",
    "created_at": "2026-03-20T10:30:00Z",
    "updated_at": "2026-03-25T14:15:00Z"
  }
]
```

**Errors:**
- `401` — not authenticated
- `403` — insufficient role

---

#### **1.2 Create a New Zone Version**

```http
PUT /api_v2/zones
Content-Type: application/json
```

**Request Body:**
```json
{
  "city_key": "los_angeles",
  "name": "LA Zones v2"
}
```

**Response:** `200 OK`
```json
{
  "id": 2,
  "team_id": 42,
  "city_key": "los_angeles",
  "name": "LA Zones v2",
  "version": 1,
  "is_active": false,
  "created_by": "admin@company.com",
  "created_at": "2026-03-29T15:00:00Z",
  "updated_at": "2026-03-29T15:00:00Z"
}
```

**Validation Errors:** `400 Bad Request`
- Missing `city_key` or `name`
- `name` is empty or whitespace-only

---

#### **1.3 Ensure First Version (Create or Return)**

```http
POST /api_v2/zones/ensure-first-version
Content-Type: application/json
```

**Request Body:**
```json
{
  "city_key": "san_francisco"
}
```

**Response:** `200 OK`  
Returns the first version for the city if it exists; otherwise creates it with name `"{city_key} Zones v1"`.

---

#### **1.4 Activate a Zone Version**

```http
PATCH /api_v2/zones/{version_id}/activate
```

**Path Parameters:**
- `version_id` (required) — ID of the zone version to activate

**Response:** `200 OK`
```json
{
  "id": 1,
  "team_id": 42,
  "city_key": "new_york",
  "name": "NY Zones v1",
  "version": 1,
  "is_active": true,
  "updated_at": "2026-03-29T15:05:00Z"
}
```

**Validation Errors:** `400 Bad Request`
- Version already active

**Not Found:** `404`
- Version ID doesn't exist or belongs to different team

---

### 2. Zone Management (Within a Version)

#### **2.1 List All Zones in a Version**

```http
GET /api_v2/zones/{version_id}/zones
```

**Path Parameters:**
- `version_id` (required) — zone version ID

**Response:** `200 OK`
```json
[
  {
    "id": 101,
    "name": "Chelsea",
    "zone_type": "user",
    "centroid_lat": 40.748,
    "centroid_lng": -73.968,
    "geometry": { /* GeoJSON MultiPolygon */ },
    "geometry_simplified": { /* simplified GeoJSON */ },
    "min_lat": 40.745,
    "max_lat": 40.752,
    "min_lng": -73.972,
    "max_lng": -73.964,
    "is_active": true,
    "created_at": "2026-03-28T09:30:00Z",
    "template": {
      "id": 1001,
      "zone_id": 101,
      "name": "Chelsea Standard",
      "version": 2,
      "is_active": true,
      "default_facility_id": 5,
      "max_orders_per_route": 15,
      "max_vehicles": 3,
      "operating_window_start": "08:00",
      "operating_window_end": "18:00",
      "eta_tolerance_seconds": 300,
      "vehicle_capabilities_required": ["cold_chain"],
      "preferred_vehicle_ids": [10, 11],
      "default_route_end_strategy": "round_trip",
      "meta": { /* optional config */ },
      "created_at": "2026-03-29T14:00:00Z",
      "updated_at": "2026-03-29T14:00:00Z"
    }
  }
]
```

**Errors:**
- `404` — version not found or doesn't belong to team

---

#### **2.2 Create a Zone**

```http
PUT /api_v2/zones/{version_id}/zones
Content-Type: application/json
```

**Path Parameters:**
- `version_id` (required) — zone version ID

**Request Body:**
```json
{
  "name": "Downtown",
  "zone_type": "user",
  "centroid_lat": 40.7128,
  "centroid_lng": -74.0060,
  "geometry": {
    "type": "MultiPolygon",
    "coordinates": [
      [
        [
          [-74.0060, 40.7128],
          [-74.0050, 40.7128],
          [-74.0050, 40.7138],
          [-74.0060, 40.7138],
          [-74.0060, 40.7128]
        ]
      ]
    ]
  },
  "min_lat": 40.7120,
  "max_lat": 40.7145,
  "min_lng": -74.0070,
  "max_lng": -74.0045
}
```

**Request Fields:**

| Field | Type | Required | Rules | Notes |
|---|---|---|---|---|
| `name` | string | ✓ | Non-empty; ≤ 255 chars | Zone identifier |
| `zone_type` | enum | | One of: `bootstrap`, `system`, `user` | Defaults to `user` |
| `centroid_lat` | number | | Latitude of zone center | Optional but recommended for mapping |
| `centroid_lng` | number | | Longitude of zone center | Optional but recommended for mapping |
| `geometry` | GeoJSON | | Valid MultiPolygon | Optional; use if zone has defined boundary |
| `min_lat` | number | | Minimum latitude boundary | Denormalized; auto-calculated from geometry if provided |
| `max_lat` | number | | Maximum latitude boundary | Denormalized; auto-calculated from geometry if provided |
| `min_lng` | number | | Minimum longitude boundary | Denormalized; auto-calculated from geometry if provided |
| `max_lng` | number | | Maximum longitude boundary | Denormalized; auto-calculated from geometry if provided |

**Response:** `200 OK`
```json
{
  "id": 102,
  "team_id": 42,
  "zone_version_id": 1,
  "city_key": "new_york",
  "name": "Downtown",
  "zone_type": "user",
  "centroid_lat": 40.7128,
  "centroid_lng": -74.0060,
  "geometry": { /* GeoJSON */ },
  "min_lat": 40.7120,
  "max_lat": 40.7145,
  "min_lng": -74.0070,
  "max_lng": -74.0045,
  "is_active": true,
  "created_at": "2026-03-29T15:10:00Z",
  "template": null
}
```

**Validation Errors:** `400 Bad Request`
- Missing `name`
- `name` is empty/whitespace
- Invalid `zone_type`

**Not Found:** `404`
- Version doesn't exist or belongs to different team

---

#### **2.3 Update Zone Name**

```http
PATCH /api_v2/zones/{version_id}/zones/{zone_id}
Content-Type: application/json
```

**Path Parameters:**
- `version_id` (required) — zone version ID
- `zone_id` (required) — zone ID to update

**Request Body:**
```json
{
  "name": "Downtown Updated"
}
```

**Response:** `200 OK`  
Same as Zone Creation response with updated `name` and `updated_at` timestamp.

**Validation Errors:** `400 Bad Request`
- Missing `name`
- `name` is empty/whitespace

**Not Found:** `404`
- Zone doesn't exist or doesn't belong to version

---

#### **2.4 Update Zone Geometry**

```http
PATCH /api_v2/zones/{version_id}/zones/{zone_id}/geometry
Content-Type: application/json
```

**Path Parameters:**
- `version_id` (required) — zone version ID
- `zone_id` (required) — zone ID

**Request Body:**
```json
{
  "geometry": {
    "type": "MultiPolygon",
    "coordinates": [/* updated coordinates */]
  },
  "centroid_lat": 40.7135,
  "centroid_lng": -74.0055,
  "min_lat": 40.7100,
  "max_lat": 40.7170,
  "min_lng": -74.0080,
  "max_lng": -74.0030
}
```

**Request Fields:**  
All geometry fields are optional; provide any combination that applies to your update.

| Field | Type | Optional | Notes |
|---|---|---|---|
| `geometry` | GeoJSON | | Valid MultiPolygon; triggers derivative updates |
| `centroid_lat` | number | | Latitude |
| `centroid_lng` | number | | Longitude |
| `min_lat` | number | | Minimum latitude |
| `max_lat` | number | | Maximum latitude |
| `min_lng` | number | | Minimum longitude |
| `max_lng` | number | | Maximum longitude |

**Response:** `200 OK`  
Same as Zone Creation response with updated geometry fields.

**Constraints:**
- **Can only be done on inactive zone versions**. If you try to update geometry on an active version, you'll receive:

```
400 Bad Request
{
  "error": "Cannot edit zone geometry in an active version. Create a new version to redraw zone boundaries."
}
```

**Validation Errors:** `400 Bad Request`
- At least one geometry field must be provided
- Invalid GeoJSON (if `geometry` is provided)

**Not Found:** `404`
- Zone doesn't exist

---

#### **2.5 Delete a Zone**

```http
DELETE /api_v2/zones/{version_id}/zones/{zone_id}
```

**Path Parameters:**
- `version_id` (required) — zone version ID
- `zone_id` (required) — zone ID to delete

**Response:** `200 OK`
```json
{
  "message": "Zone deleted successfully"
}
```

**Errors:**
- `404` — zone not found

---

### 3. Zone Template Management

A **Zone Template** defines operational defaults for routing within a zone:
- Facility anchor (where orders dispatch from)
- Route sizing (max orders per route, max vehicle count)
- Operating hours (when routes can run)
- Vehicle requirements (capabilities, preferred vehicles)
- Route behavior (end strategy)

#### **3.1 Get Zone Template**

```http
GET /api_v2/zones/{version_id}/zones/{zone_id}/template
```

**Path Parameters:**
- `version_id` (required)
- `zone_id` (required)

**Response:** `200 OK`
```json
{
  "id": 1001,
  "team_id": 42,
  "zone_id": 101,
  "name": "Chelsea Standard",
  "version": 2,
  "is_active": true,
  "default_facility_id": 5,
  "max_orders_per_route": 15,
  "max_vehicles": 3,
  "operating_window_start": "08:00",
  "operating_window_end": "18:00",
  "eta_tolerance_seconds": 300,
  "vehicle_capabilities_required": ["cold_chain"],
  "preferred_vehicle_ids": [10, 11],
  "default_route_end_strategy": "round_trip",
  "meta": null,
  "created_at": "2026-03-29T14:00:00Z",
  "updated_at": "2026-03-29T14:00:00Z"
}
```

**Errors:**
- `404` — zone not found or no template exists

---

#### **3.2 Create or Update Zone Template**

```http
PUT /api_v2/zones/{version_id}/zones/{zone_id}/template
Content-Type: application/json
```

**Path Parameters:**
- `version_id` (required)
- `zone_id` (required)

**Request Body:**
```json
{
  "name": "Chelsea Standard",
  "default_facility_id": 5,
  "max_orders_per_route": 15,
  "max_vehicles": 3,
  "operating_window_start": "08:00",
  "operating_window_end": "18:00",
  "eta_tolerance_seconds": 300,
  "vehicle_capabilities_required": ["cold_chain"],
  "preferred_vehicle_ids": [10, 11],
  "default_route_end_strategy": "round_trip",
  "meta": {
    "custom_field": "custom_value"
  }
}
```

**Request Fields:**

| Field | Type | Required | Rules | Notes |
|---|---|---|---|---|
| `name` | string | ✓ | Non-empty; ≤ 255 chars | Template identifier |
| `default_facility_id` | integer | | Positive; must exist | Facility where orders dispatch from |
| `max_orders_per_route` | integer | | ≥ 1 | Upper limit on orders per route solution |
| `max_vehicles` | integer | | ≥ 1 | Upper limit on number of routes created |
| `operating_window_start` | string | | HH:MM format (24-hour) | When routes can start |
| `operating_window_end` | string | | HH:MM format; must be after start | When routes must end |
| `eta_tolerance_seconds` | integer | | 0–7200 | Acceptable deviation from ETA; defaults to 0 |
| `vehicle_capabilities_required` | array | | List of valid capability strings | All vehicles assigned must have all capabilities; see Allowed Capabilities below |
| `preferred_vehicle_ids` | array | | List of positive integers | Vehicle IDs within team; soft preference |
| `default_route_end_strategy` | string | | One of: `round_trip`, `custom_end_address`, `end_at_last_stop`, `last_stop` | Strategy for route completion; `last_stop` alias for `end_at_last_stop` |
| `meta` | object | | Any JSON object | Escape hatch for future config |

**Allowed Capabilities:**  
- `cold_chain`
- `fragile`
- (more as defined in system)

**Route End Strategy Values:**

| Value | Alias | Meaning |
|---|---|---|
| `round_trip` | — | Return to facility/hub after last delivery |
| `custom_end_address` | — | End at a specified address provided at route creation |
| `end_at_last_stop` | `last_stop` | End at the location of the last delivery |

Both `end_at_last_stop` and the friendly alias `last_stop` are accepted and normalized to the same constant.

**Response:** `200 OK`  
Same structure as Get Zone Template response with updated `version`, `is_active: true`, and new `created_at`/`updated_at`.

**Behavior on Update:**
- If a template already exists and is active, a new version is created automatically
- The new version becomes active; the old one is deactivated
- Version counter increments on each update

**Validation Errors:** `400 Bad Request`
- Missing `name`
- `operating_window_end` before `operating_window_start`
- Invalid `eta_tolerance_seconds` (outside 0–7200 range)
- Invalid `vehicle_capabilities_required` — unknown capability name
- Invalid `default_route_end_strategy` — not one of the allowed values
- `default_facility_id` refers to facility that doesn't exist (or belongs to different team)

**Not Found:** `404`
- Zone doesn't exist

---

## Error Handling

All endpoints return errors in this format:

```json
{
  "error": "Human-readable error message",
  "type": "ValidationFailed|NotFound|PermissionDenied|ServerError",
  "details": { }
}
```

### Common HTTP Status Codes

| Code | Meaning | When |
|---|---|---|
| `200` | OK | Successful operation |
| `400` | Bad Request | Validation error in request |
| `401` | Unauthorized | Missing or invalid JWT |
| `403` | Forbidden | Insufficient role |
| `404` | Not Found | Resource doesn't exist or doesn't belong to team |
| `500` | Internal Server Error | Unplanned failure (report to backend team) |

---

## Workflow Examples

### Example 1: Create a New City's Zone System

```bash
# 1. Create a new zone version for a city
PUT /api_v2/zones
{
  "city_key": "chicago",
  "name": "Chicago Zones v1"
}
# Response: version_id = 10, is_active = false

# 2. Create zones within that version
PUT /api_v2/zones/10/zones
{
  "name": "Loop",
  "zone_type": "user",
  "centroid_lat": 41.8863,
  "centroid_lng": -87.6233,
  "geometry": { /* ... */ }
}
# Response: zone_id = 201

# 3. Create a template for the zone
PUT /api_v2/zones/10/zones/201/template
{
  "name": "Loop Standard Routing",
  "default_facility_id": 3,
  "max_orders_per_route": 20,
  "max_vehicles": 4,
  "operating_window_start": "07:00",
  "operating_window_end": "19:00",
  "eta_tolerance_seconds": 120,
  "default_route_end_strategy": "round_trip"
}

# 4. Activate the version when ready
PATCH /api_v2/zones/10/activate
```

---

### Example 2: Edit Zone Geometry (In Inactive Version)

```bash
# 1. Create new version (copy of old one, or new from scratch)
PUT /api_v2/zones
{
  "city_key": "chicago",
  "name": "Chicago Zones v2"
}
# Response: version_id = 11, is_active = false

# 2. List zones and copy/create zones as needed
# (Details omitted for brevity)

# 3. Update zone geometry while inactive
PATCH /api_v2/zones/11/zones/202/geometry
{
  "geometry": { /* new GeoJSON */ },
  "min_lat": 41.88,
  "max_lat": 41.89,
  "min_lng": -87.63,
  "max_lng": -87.62
}

# 4. Activate the new version when ready
PATCH /api_v2/zones/11/activate
```

---

### Example 3: Update Route Strategy for a Zone

```bash
# Get current template (to see current state)
GET /api_v2/zones/10/zones/201/template

# Update template with new strategy
PUT /api_v2/zones/10/zones/201/template
{
  "name": "Loop Standard Routing",
  "default_facility_id": 3,
  "max_orders_per_route": 20,
  "max_vehicles": 4,
  "operating_window_start": "07:00",
  "operating_window_end": "19:00",
  "eta_tolerance_seconds": 120,
  "default_route_end_strategy": "end_at_last_stop",
  "vehicle_capabilities_required": ["cold_chain"],
  "preferred_vehicle_ids": [15, 16]
}
# Response: new template with version = 2, updated fields
```

---

## Key Design Notes

**1. Versions are Immutable Once Active**
- Geometry edits require creating a new inactive version, editing there, then activating
- Zone definitions (name, type) can be edited in active versions
- Think of an "active version" as a published configuration

**2. Zone Templates Auto-Version**
- Each time you update a template, a new version is created automatically
- Only one template per zone is active at a time
- The active one is always the latest

**3. Facility and Vehicle Validation**
- `default_facility_id` in templates must point to an existing Facility
- `preferred_vehicle_ids` must be valid Vehicle IDs in your team
- System validates these at the command layer (service layer)

**4. Operating Windows**
- Use 24-hour HH:MM format (e.g., "08:00", "18:30")
- If both start and end are provided, end must be strictly after start
- Leave both as `null` if no time-based restriction

**5. Route End Strategy Flexibility**
- Frontend can use user-friendly name `"last_stop"` — backend normalizes it
- For compatibility with direct route creation (without zones), both forms are accepted
- Always stored/returned as `"end_at_last_stop"` in responses

---

## Field Constraints Summary

| Field | Min | Max | Pattern |
|---|---|---|---|
| `name` (zone, template) | 1 char | 255 chars | Non-empty string |
| `city_key` | — | — | Any string |
| `centroid_lat` / `min_lat` / `max_lat` | -90 | 90 | Valid latitude |
| `centroid_lng` / `min_lng` / `max_lng` | -180 | 180 | Valid longitude |
| `max_orders_per_route` | 1 | — | Positive integer |
| `max_vehicles` | 1 | — | Positive integer |
| `eta_tolerance_seconds` | 0 | 7200 | Non-negative integer ≤ 2 hours |
| `operating_window_start/end` | — | — | HH:MM (24-hour) |
| `preferred_vehicle_ids[*]` | 1 | — | Positive integer |

---

## Testing Checklist for Frontend

After implementing these endpoints, verify:

- [ ] Can create zone version
- [ ] Can list zone versions filtered by city_key
- [ ] Can activate/deactivate versions
- [ ] Can create zone with geometry
- [ ] Can update zone name
- [ ] Can update zone geometry (only in inactive version)
- [ ] Can delete zone
- [ ] Can create zone template with all fields
- [ ] Can update zone template (increments version automatically)
- [ ] Template accepts both `"last_stop"` and `"end_at_last_stop"` for route strategy
- [ ] Invalid facility_id rejected with 400
- [ ] Invalid dates rejected (end before start)
- [ ] Geometry edit on active version rejected with 400
- [ ] Missing `name` rejected with 400
- [ ] Invalid capabilities rejected with 400
- [ ] Response shapes match documentation

---

## Questions or Issues?

Refer to the backend implementation docs:
- [Zone Template Service Refactor](../implemented/ZONE_TEMPLATE_SERVICE_REFACTOR.md) — how request parsing and serialization work
- [API_MIGRATION_GUIDE.md](../API_MIGRATION_GUIDE.md) — context on schema changes
