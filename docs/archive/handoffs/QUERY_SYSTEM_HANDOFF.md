# Frontend Handoff: Query System for Zones, Vehicles & Facilities

**Date:** March 29, 2026  
**Status:** ✅ Ready for Implementation  
**Pattern:** Shopify-Style Search with Column Narrowing

---

## Table of Contents

1. [Overview](#overview)
2. [Query Pattern](#query-pattern)
3. [Zone Queries](#zone-queries)
4. [Vehicle Queries](#vehicle-queries)
5. [Facility Queries](#facility-queries)
6. [Common Patterns](#common-patterns)
7. [Error Handling](#error-handling)
8. [Implementation Checklist](#implementation-checklist)

---

## Overview

The query system uses a **Shopify-style search pattern** where you can:

- **Search broadly** with a single `q` parameter across multiple columns
- **Narrow results** with an optional `s` parameter to specify which columns to search
- **Combine** text search + exact filters for precise results
- **Paginate efficiently** using opaque ID-based cursors

This enables intuitive search UI while maintaining query efficiency.

---

## Query Pattern

### The Two-Parameter Model

Every `find_*` endpoint supports two key parameters:

#### `q` — General Search Query

Searches across multiple pre-defined columns in a single call.

```
?q=electric
→ searches all string columns: registration_number, label, fuel_type, travel_mode, status
```

**Rules:**
- Case-insensitive substring match (`ILIKE` in SQL)
- Only applies when parameter is provided
- Searches all specified columns by OR logic (any match qualifies)

---

#### `s` — Column Selector (Optional)

Narrows the `q` search to specific columns.

```
?q=electric&s=fuel_type
→ searches only fuel_type column for "electric"

?q=idle&s=status,fuel_type
→ searches status OR fuel_type for "idle"
```

**Rules:**
- Comma-separated string or JSON array format
- Only applies when `q` is present
- If omitted, `q` searches all default columns
- Unknown column names are silently ignored

---

### Examples of the Pattern

**Without narrowing (searches all columns):**
```
GET /api_v2/vehicles?q=electric
→ searches: registration_number, label, fuel_type, travel_mode, status
```

**With narrowing (single column):**
```
GET /api_v2/vehicles?q=electric&s=fuel_type
→ searches only: fuel_type
```

**With multiple columns:**
```
GET /api_v2/vehicles?q=idle&s=status,fuel_type
→ searches: status OR fuel_type
```

**Combined with exact filters:**
```
GET /api_v2/vehicles?q=electric&is_active=true&status=idle
→ searches q across columns AND is_active==true AND status==idle
```

---

## Zone Queries

### Endpoint: List/Search Zones

```http
GET /api_v2/zones/{version_id}/zones
```

### Searchable Columns (with `q`)

| Column | Description |
|--------|-------------|
| `name` | Zone name |
| `city_key` | City identifier |
| `zone_type` | Zone classification |

### Exact Filter Parameters

| Parameter | Type | Values | Notes |
|-----------|------|--------|-------|
| `version_id` | integer | — | Filter by zone version (many zones can belong to one version) |
| `zone_type` | string | bootstrap, system, user | Exact match on zone type |
| `is_active` | boolean | true, false | Active/inactive zones |
| `city_key` | string | — | Substring match on city |

### Examples

#### Search all zones in a version
```
GET /api_v2/zones/5/zones
```

#### Search by zone name
```
GET /api_v2/zones/5/zones?q=downtown
```

#### Search only by city
```
GET /api_v2/zones/5/zones?q=NYC&s=city_key
```

#### Find user-created zones only
```
GET /api_v2/zones/5/zones?zone_type=user
```

#### Find active zones matching name
```
GET /api_v2/zones/5/zones?q=east&is_active=true
```

#### Search across name and city only
```
GET /api_v2/zones/5/zones?q=chicago&s=name,city_key
```

---

## Vehicle Queries

### Endpoint: List/Search Vehicles

```http
GET /api_v2/vehicles
```

### Searchable Columns (with `q`)

| Column | Description |
|--------|-------------|
| `registration_number` | License plate / registration |
| `label` | Vehicle nickname/label |
| `fuel_type` | Type of fuel |
| `travel_mode` | Mode of travel |
| `status` | Operational state |

### Exact Filter Parameters

| Parameter | Type | Values | Notes |
|-----------|------|--------|-------|
| `team_id` | integer | — | Team scope (usually auto-injected) |
| `client_id` | string | — | Filter by client |
| `travel_mode` | string | car, truck, bicycle, motorcycle, etc. | Exact match |
| `status` | string | idle, in_route, loading, offline, maintenance | Exact match |
| `fuel_type` | string | gasoline, diesel, electric, hybrid, etc. | Exact match |
| `is_active` | boolean | true, false | Active/inactive vehicles |
| `home_facility_id` | integer | — | Filter by home facility |

### Examples

#### List all vehicles
```
GET /api_v2/vehicles
```

#### Search across all columns
```
GET /api_v2/vehicles?q=electric
→ matches: registration "electric123", label "electric van", fuel_type "electric", etc.
```

#### Search only fuel type
```
GET /api_v2/vehicles?q=electric&s=fuel_type
→ matches only vehicles with fuel_type containing "electric"
```

#### Search registration number
```
GET /api_v2/vehicles?q=ABC123&s=registration_number
```

#### Find idle vehicles
```
GET /api_v2/vehicles?q=idle&s=status
→ matches: status exactly equals "idle" (but uses search pattern)
```

#### Find active electric vehicles
```
GET /api_v2/vehicles?q=electric&fuel_type=electric&is_active=true
```

#### Find vehicles by home facility
```
GET /api_v2/vehicles?home_facility_id=5
```

#### Find vehicles by travel mode
```
GET /api_v2/vehicles?travel_mode=truck
```

#### Complex: Electric vehicles that are active and idle
```
GET /api_v2/vehicles?q=electric&s=fuel_type&status=idle&is_active=true
```

---

## Facility Queries

### Endpoint: List/Search Facilities

```http
GET /api_v2/facilities
```

### Searchable Columns (with `q`)

| Column | Description |
|--------|-------------|
| `name` | Facility name |
| `facility_type` | Type of facility |
| `client_id` | Client identifier |

### Exact Filter Parameters

| Parameter | Type | Values | Notes |
|-----------|------|--------|-------|
| `team_id` | integer | — | Team scope (usually auto-injected) |
| `client_id` | string | — | Exact match on client |
| `facility_type` | string | warehouse, depot, hub, pickup_point | Exact match |
| `can_dispatch` | boolean | true, false | Can dispatch orders |
| `can_receive_returns` | boolean | true, false | Can receive returns |

### Examples

#### List all facilities
```
GET /api_v2/facilities
```

#### Search by name
```
GET /api_v2/facilities?q=main
```

#### Search across all columns
```
GET /api_v2/facilities?q=warehouse
→ matches: name "Main Warehouse", facility_type "warehouse", etc.
```

#### Search only by facility type
```
GET /api_v2/facilities?q=hub&s=facility_type
```

#### Find dispatching locations
```
GET /api_v2/facilities?can_dispatch=true
```

#### Find warehouses only
```
GET /api_v2/facilities?facility_type=warehouse
```

#### Find active return facilities
```
GET /api_v2/facilities?can_receive_returns=true
```

#### Search for hubs that dispatch
```
GET /api_v2/facilities?q=hub&facility_type=hub&can_dispatch=true
```

#### Find by client and capability
```
GET /api_v2/facilities?client_id=c123&can_dispatch=true
```

---

## Common Patterns

### Pattern 1: Simple Text Search (All Columns)

**Goal:** Quick search without knowing exact field

```javascript
// User types "electric" — search all fields
GET /api_v2/vehicles?q=electric

// Returns any vehicle matching "electric" in any string column
```

---

### Pattern 2: Narrow to Specific Column

**Goal:** Reduce false positives by narrowing to known field

```javascript
// Instead of searching all columns, search only fuel_type
GET /api_v2/vehicles?q=electric&s=fuel_type

// Returns only vehicles where fuel_type contains "electric"
// (ignores matches in label, registration_number, etc.)
```

---

### Pattern 3: Multiple Column Search

**Goal:** Search within a subset of columns

```javascript
// Search vehicles by registration OR label only
GET /api_v2/vehicles?q=VAN&s=registration_number,label

// Useful when you want to exclude fuel_type, travel_mode, status
```

---

### Pattern 4: Text Search + Exact Filters

**Goal:** Combine fuzzy search with precise filtering

```javascript
// Find electric vehicles that are currently idle
GET /api_v2/vehicles?q=electric&s=fuel_type&status=idle

// Find facilities named "main" that are hubs and can dispatch
GET /api_v2/facilities?q=main&s=name&facility_type=hub&can_dispatch=true

// Find user zones in NYC
GET /api_v2/zones/5/zones?q=NYC&s=city_key&zone_type=user
```

---

### Pattern 5: Enum/Boolean Filters Only (No Text Search)

**Goal:** Filter by exact values only

```javascript
// Find all idle vehicles
GET /api_v2/vehicles?status=idle

// Find all dispatching facilities
GET /api_v2/facilities?can_dispatch=true

// Find all user zones
GET /api_v2/zones/5/zones?zone_type=user

// No `q` parameter → no text search, just exact filters
```

---

### Pattern 6: Pagination

**Goal:** Load results in pages

```javascript
// First request — get initial results
GET /api_v2/vehicles?q=electric&limit=20

// Next request — continue from last ID
GET /api_v2/vehicles?q=electric&limit=20&cursor=xyz123

// All find functions support opaque cursor-based pagination
```

---

## Error Handling

### Valid but Empty Results

```json
{
  "data": [],
  "pagination": {
    "cursor": null,
    "has_more": false
  }
}
```

**Meaning:** Query is valid but no results match. Not an error.

---

### Client Error (e.g., invalid column in `s`)

```javascript
GET /api_v2/vehicles?q=electric&s=unknown_column
```

**Result:** Unknown column is silently ignored; search continues with other columns.

---

### Validation Error (provided in response, not 400 error)

```json
{
  "error": "invalid value for is_active: must be true or false",
  "type": "ValidationFailed"
}
```

---

## Implementation Checklist

### Frontend Developer Setup

- [ ] Understand the `q` parameter (general search)
- [ ] Understand the `s` parameter (column narrowing)
- [ ] Know the searchable columns for each entity type
- [ ] Know the exact filter parameters for each entity type
- [ ] Implement UI search boxes that send `q` parameter
- [ ] Implement optional filter UI that sends specific parameters
- [ ] Handle pagination (opaque cursor-based)
- [ ] Display results as list/cards
- [ ] Handle empty results gracefully

### Zone Search UI

- [ ] Create search box that sends `?q={query}` to `/api_v2/zones/{version_id}/zones`
- [ ] Add filter for `zone_type` (dropdown: user, system, bootstrap)
- [ ] Add filter for `is_active` (toggle: active/inactive)
- [ ] Show results with: name, city_key, zone_type, template info
- [ ] Test searches: "downtown", "chicago", etc.

### Vehicle Search UI

- [ ] Create search box that sends `?q={query}` to `/api_v2/vehicles`
- [ ] Add filters:
  - `fuel_type` (dropdown or autocomplete)
  - `status` (dropdown: idle, in_route, loading, offline, maintenance)
  - `is_active` (toggle)
  - `home_facility_id` (facility picker)
- [ ] Show results with: registration_number, label, fuel_type, status, is_active
- [ ] Test searches: "electric", "van", "123", etc.
- [ ] Test filters: status=idle, is_active=true, etc.

### Facility Search UI

- [ ] Create search box that sends `?q={query}` to `/api_v2/facilities`
- [ ] Add filters:
  - `facility_type` (dropdown: warehouse, depot, hub, pickup_point)
  - `can_dispatch` (toggle)
  - `can_receive_returns` (toggle)
- [ ] Show results with: name, facility_type, can_dispatch, can_receive_returns
- [ ] Test searches: "main", "warehouse", "hub", etc.

### Testing Scenarios

**Zone Search:**
- [ ] `?q=chicago` → finds zones matching city_key or name
- [ ] `?q=chicago&s=city_key` → finds only by city_key
- [ ] `?zone_type=user` → finds only user zones
- [ ] `?q=east&zone_type=user&is_active=true` → combined filters

**Vehicle Search:**
- [ ] `?q=electric` → finds across all columns
- [ ] `?q=electric&s=fuel_type` → finds only fuel_type
- [ ] `?status=idle` → finds idle vehicles
- [ ] `?q=electric&status=idle&is_active=true` → combined

**Facility Search:**
- [ ] `?q=main` → finds matching name
- [ ] `?facility_type=hub` → finds all hubs
- [ ] `?can_dispatch=true` → finds dispatching facilities
- [ ] `?q=warehouse&facility_type=warehouse&can_dispatch=true` → combined

---

## API Reference Summary

### Zones

```
GET /api_v2/zones                           # List all zone versions (filter: city_key)
GET /api_v2/zones/{version_id}/zones        # List zones + search (q, s, zone_type, is_active, city_key)
```

**Searchable:** name, city_key, zone_type

---

### Vehicles

```
GET /api_v2/vehicles                        # List vehicles + search (q, s, status, fuel_type, etc.)
```

**Searchable:** registration_number, label, fuel_type, travel_mode, status

---

### Facilities

```
GET /api_v2/facilities                      # List facilities + search (q, s, facility_type, etc.)
```

**Searchable:** name, facility_type, client_id

---

## Tips & Best Practices

### 1. **Start with `q` Only, Add `s` if Needed**

```javascript
// First: user types "electric"
GET /api_v2/vehicles?q=electric

// If too many results, narrow:
GET /api_v2/vehicles?q=electric&s=fuel_type
```

### 2. **Use Dropdowns for Exact Filters**

```javascript
// Don't send region=east (not a real parameter)
// Instead use exact filters:
GET /api_v2/zones/5/zones?zone_type=user   // dropdown
GET /api_v2/vehicles?status=idle            // dropdown
GET /api_v2/facilities?can_dispatch=true    // toggle
```

### 3. **Combine Text + Filters**

```javascript
// Text search + exact filter = powerful UX
GET /api_v2/vehicles?q=electric&fuel_type=electric&is_active=true
// User sees: "electric" vehicles that are currently active
```

### 4. **Handle Empty Results**

```javascript
if (response.data.length === 0) {
  message = `No ${entity}s found matching "${query}". Try:
    - Broadening your search
    - Adjusting filters
    - Checking spelling`;
}
```

### 5. **Validate Column Names in `s`**

Frontend does not need to validate — backend silently ignores unknown columns. But do log it for debugging:

```javascript
const validColumns = {
  vehicles: ['registration_number', 'label', 'fuel_type', 'travel_mode', 'status'],
  facilities: ['name', 'facility_type', 'client_id'],
  zones: ['name', 'city_key', 'zone_type']
};

// Warn if user sends invalid column
if (!validColumns.vehicles.includes(userColumn)) {
  console.warn(`Unknown column: ${userColumn}`);
}
```

---

## Questions?

Refer to:
- **Backend Implementation:** `/docs/implemented/ZONE_TEMPLATE_SERVICE_REFACTOR.md`
- **Zone API Details:** `/docs/handoffs_to_front_end/ZONE_API_FRONTEND_GUIDE.md`
- **Shopify-Style Query System:** This document

**Contact Backend Team:** For questions on endpoint behavior or parameter validation.

---

## Version History

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-29 | 1.0 | Initial handoff — Shopify-style query system |

