# Zone Edit Endpoints — Split Handoff (Backend → Frontend)

Created: 2026-03-28
Scope: Zone name editing and zone geometry editing are now separate endpoints
Backend source plan: `Back_end/docs/archive/ZONE_EDIT_SPLIT_PLAN_2026-03-28.md`
Frontend architecture reference: `Front_end/admin-app/docs/implemented/ZONE_ROUTEGROUP_ARCHITECTURE.md`
Previous zone handoff: `Front_end/admin-app/docs/handoff_from_backend/ZONES_ENDPOINT_HANDOFF_2026-03-27_13-07-56.md`

---

## What Changed and Why

The previous `PATCH /api_v2/zones/{version_id}/zones/{zone_id}` handled both name and geometry
in a single endpoint, with a blanket guard blocking all edits on active zone versions.

This is being split into two endpoints with independent rules:

| Endpoint | Fields | Active version allowed? |
|---|---|---|
| `PATCH /zones/{version_id}/zones/{zone_id}` | `name` only | **Yes** |
| `PATCH /zones/{version_id}/zones/{zone_id}/geometry` | `geometry`, centroid, bounding box | **No — inactive versions only** |
| `PUT /zones/{version_id}/zones/{zone_id}/template` | template config | **Yes** (unchanged) |

### Why name edits are unrestricted

Zone name is metadata. The name is snapshotted into any RouteGroup at materialization time —
historical groups are never affected. Fixing "Stockholm Nort" → "Stockholm North" on a live zone
is safe and should not require creating a new version.

### Why geometry edits remain restricted

Geometry changes affect which orders get spatially assigned to the zone going forward. Redrawing
a live zone boundary during an active delivery day is an intentional operator decision, not a
routine edit. Creating a new version remains the correct path for geometry changes.

### Template config is unchanged

`PUT /api_v2/zones/{version_id}/zones/{zone_id}/template` already had no version restriction
and already self-versions. Nothing changes here.

---

## 1 — Update Zone Name

**Method:** `PATCH`
**Path:** `/api_v2/zones/{version_id}/zones/{zone_id}`
**Roles:** ADMIN
**Active version allowed:** Yes

### Request body

```typescript
interface UpdateZoneNamePayload {
  name: string   // required, non-empty
}
```

Only `name` is accepted. Sending other fields does not cause an error — they are ignored.

### Success response

```json
{
  "data": {
    "id": 7,
    "team_id": 1,
    "zone_version_id": 12,
    "city_key": "stockholm",
    "name": "Stockholm North",
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
  },
  "warnings": []
}
```

### Validation errors

| Condition | Status | Message |
|---|---|---|
| `name` absent or empty string | 410 | `name must be a non-empty string` |
| Zone not found or wrong team | 414 | `Zone {id} not found` |
| `version_id` path param does not match zone's version | 414 | `Zone {id} not found` |

---

## 2 — Update Zone Geometry

**Method:** `PATCH`
**Path:** `/api_v2/zones/{version_id}/zones/{zone_id}/geometry`
**Roles:** ADMIN
**Active version allowed:** No — returns 410 if zone belongs to an active version

### Request body

```typescript
interface UpdateZoneGeometryPayload {
  geometry?: GeoJSONPolygon
  centroid_lat?: number
  centroid_lng?: number
  min_lat?: number
  max_lat?: number
  min_lng?: number
  max_lng?: number
}
```

At least one field must be present. All are optional individually but the payload cannot be empty.

The client is responsible for computing and sending updated centroid and bounding box when
geometry changes — same pattern as zone creation.

### Success response

Same shape as Update Zone Name above. Returns the full serialized zone.

### Validation errors

| Condition | Status | Message |
|---|---|---|
| Zone belongs to an active version | 410 | `Cannot edit zone geometry in an active version. Create a new version to redraw zone boundaries.` |
| No spatial fields in payload | 410 | `No geometry fields provided.` |
| Zone not found or wrong team | 414 | `Zone {id} not found` |
| `version_id` path param does not match zone's version | 414 | `Zone {id} not found` |

---

## 3 — Update Zone Template Config (Unchanged)

**Method:** `PUT`
**Path:** `/api_v2/zones/{version_id}/zones/{zone_id}/template`
**Active version allowed:** Yes

No changes. This endpoint already supports editing template config on active zones.
Refer to the previous handoff document for the full contract.

---

## Frontend Adaptation

### API client (`zone.api.ts`)

The existing `updateZone` call (previously PATCH with name + geometry) must be split:

```typescript
// Rename existing to updateZoneName — name only, always available
updateZoneName(versionId: number, zoneId: number, payload: { name: string }): Promise<ZoneDefinition>

// Add new for geometry — only callable when version is inactive
updateZoneGeometry(versionId: number, zoneId: number, payload: UpdateZoneGeometryPayload): Promise<ZoneDefinition>

// Unchanged
upsertZoneTemplate(versionId: number, zoneId: number, payload: ZoneTemplatePayload): Promise<ZoneTemplate>
```

### Zone edit form

The form sends two independent requests:

1. **Name field change** → `updateZoneName` — can be submitted even when the version is active
2. **Template config fields** → `upsertZoneTemplate` — can be submitted even when the version is active
3. **Geometry change** (polygon redraw on map) → `updateZoneGeometry` — must check version state before enabling

### UX guard for geometry editing

Before allowing the user to redraw a zone polygon, check `zoneVersion.is_active`:
- `is_active = false` → drawing tools enabled, `updateZoneGeometry` callable
- `is_active = true` → disable drawing tools, show inline message:
  `"Zone boundaries cannot be edited on the active version. Create a new draft version to redraw zones."`

Do not make the geometry API call speculatively — the backend will return a 410, but showing a
proactive UI block is better UX than letting the user draw and then seeing an error.

### Error handling for 410 on geometry endpoint

If the backend returns 410 on `updateZoneGeometry` (e.g. version was activated between page load
and form submit), surface the message from the error response directly:
`"Cannot edit zone geometry in an active version. Create a new version to redraw zone boundaries."`

### TypeScript types — no changes needed

`ZoneDefinition` shape is unchanged. Both edit endpoints return the same zone object shape as before.

---

## What Does NOT Change

- `PUT /zones/{version_id}/zones` — create zone, unchanged
- `DELETE /zones/{version_id}/zones/{zone_id}` — delete zone, unchanged (inactive version only)
- `GET /zones/{version_id}/zones` — list zones, unchanged
- `PATCH /zones/{version_id}/activate` — activate version, unchanged
- Template endpoints — unchanged
- Route group endpoints — unchanged
