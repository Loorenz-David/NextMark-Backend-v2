# Client Form Configuration — Backend → Frontend Handoff

Created: 2026-07-24
Scope: per-team configuration for the public client form — terms & conditions, delivery rules, and media
Migration: `cf01a2b3c4d5_add_client_form_config_tables` (adds 4 tables + 2 `order` columns)

---

## What This Is

Teams can now configure what the public client form shows:

| Thing | Cardinality | Purpose |
|---|---|---|
| **Settings** | one per team | toggles controlling which sections render |
| **Terms & conditions** | immutable version history | legal text the customer accepts at submit time |
| **Rules** | ordered list | explains how deliveries work (text + icon + optional image) |
| **Media** | ordered list per placement | branding / publicity images placed at named slots |

Two audiences:

- **Admin app** — full CRUD under `/api_v2/client_form_config/*` (authenticated).
- **Client form app** — receives the whole configuration inside the **existing** token-authenticated
  `GET /public/client-form/<token>` response under a new `config` key. There is no separate public
  config endpoint, and no endpoint anywhere accepts a `team_id` from the caller.

---

## Enums

### `placement` (media only)

The only accepted values. Anything else returns a validation error on write **and** on
`GET /media?placement=…`.

| Value | Intended slot |
|---|---|
| `carousel` | rotating gallery |
| `sidebar_left` | rail to the left of the form |
| `sidebar_right` | rail to the right of the form |

Backend source of truth: `Delivery_app_BK/services/domain/client_form/media_placement.py`.

Every placement is a side or gallery slot — none has a guaranteed position on a narrow viewport,
where there is no "beside". The form app owns that fallback (hide, or stack below the form); the
backend returns the media either way. Record the chosen behaviour here once it is decided.

There are no other enums. `icon` on a rule is a free string — the frontend decides how to map it to
an icon set.

---

## Response Envelope

Every authenticated endpoint below returns the standard envelope:

```json
{ "data": { ... }, "warnings": [] }
```

Errors return a different shape, with **offset HTTP statuses** (CloudFront intercepts 400–405):

```json
{ "error": "A client form rule already occupies that position for this team.", "code": "bad_request" }
```

| Error | HTTP | `code` |
|---|---|---|
| Validation failed | **410** | `bad_request` |
| Permission denied (wrong team / role / app scope) | **413** | `forbidden` |
| Not found | **414** | `not_found` |
| Unexpected internal error | **510** | `internal_error` |

---

## Auth

All `/api_v2/client_form_config/*` routes require:

- a valid JWT (`Authorization: Bearer …`)
- `base_role_id` ∈ `{1 (ADMIN), 2 (ASSISTANT)}` — drivers (`3`) get **413**
- admin app scope (blueprint-level guard)

Team scoping is derived from the token (`active_team_id`, falling back to `team_id`). Never send
`team_id` — it is injected server-side, and touching another team's row returns **413**.

---

## Collection Response Shape (`byClientId` / `allIds`)

`GET /rules`, `GET /media`, and `GET /terms` use the same normalized map as message templates:

```json
{
  "byClientId": { "<key>": { ...entity... } },
  "allIds": ["<key>", "<key>"]
}
```

`allIds` preserves server ordering — **use it, not `Object.keys()`**.

⚠️ **The key differs per collection:**

- **Rules and media** are keyed by `client_id` (a string you may supply on create; auto-generated otherwise).
- **Terms versions have no `client_id` column**, so they fall back to the **stringified `id`** —
  `"12"`, not `12`. Cast before lookup.

---

## Create / Update / Delete Payload Conventions

These follow the existing codebase conventions exactly.

| Verb | Body key | Shape |
|---|---|---|
| `PUT` (create) | `fields` | object, or array of objects for batch |
| `PATCH` (update) | `target` / `targets` | `{ "target_id": <id>, "fields": {...} }` |
| `DELETE` | `target_id` / `target_ids` | id, or array of ids |

⚠️ **`target_id` must be the numeric `id`.** The shared lookup helper is *meant* to also accept a
`client_id` string, but that path is broken app-wide (see *Known Backend Issue* at the end) and
currently raises a **510**. Always send the numeric `id` you got back from the create response or a
list read. This applies to every `PATCH` and `DELETE` in the API, not just these endpoints.

**Create responses** map your `client_id` → the new database `id`, so you can reconcile optimistic rows:

```json
{
  "data": {
    "ids_without_match": [],
    "rule-tmp-1": 13,
    "rule-tmp-2": 14
  },
  "warnings": []
}
```

If you omit `client_id` on create, the backend generates one (e.g.
`client_form_rule_ce2786fd29b14f89b94cdb82c7775a2d`) and keys the map by that.

---

# Admin Endpoints

Base path: `/api_v2/client_form_config`

## 1. Settings — singleton per team

### `GET /settings`

A team has **no settings row until it first saves one**. That is not an error — the endpoint returns
documented defaults with `"id": null`.

**Before first save**
```json
{
  "data": {
    "client_form_settings": {
      "id": null,
      "client_id": null,
      "updated_at": null,
      "terms_enabled": false,
      "require_acceptance": false,
      "show_rules": true,
      "show_media": true
    }
  },
  "warnings": []
}
```

**After a save**
```json
{
  "data": {
    "client_form_settings": {
      "id": 6,
      "client_id": "client_form_settings_706b1effb667487a85d7da684367cce7",
      "terms_enabled": true,
      "require_acceptance": true,
      "show_rules": true,
      "show_media": true,
      "updated_at": "2026-07-24T11:47:46.684363+00:00"
    }
  },
  "warnings": []
}
```

| Field | Type | Meaning |
|---|---|---|
| `id` | `int \| null` | `null` until first save |
| `client_id` | `string \| null` | auto-generated on first save |
| `terms_enabled` | `bool` | show the terms section at all |
| `require_acceptance` | `bool` | block submission until accepted (**only meaningful when `terms_enabled` is true**) |
| `show_rules` | `bool` | render the rules section |
| `show_media` | `bool` | render media |
| `updated_at` | ISO 8601 UTC `\| null` | |

### `PATCH /settings`

Upsert — creates the row on first call, updates it afterwards. Partial: omitted flags keep their
current values.

**Request**
```json
{ "fields": { "terms_enabled": true, "require_acceptance": true } }
```

**Response** — returns only the row id; re-fetch or patch your store locally.
```json
{ "data": { "id": 6 }, "warnings": [] }
```

Only `terms_enabled`, `require_acceptance`, `show_rules`, `show_media` are writable. Any other key
is silently ignored. There is no create or delete — the row is a singleton.

---

## 2. Terms & Conditions — immutable versions

Versions are **append-only**. Publishing never edits an existing row: it writes a new one and moves
the active flag. At most one version per team is active, enforced by a database partial unique index.

This exists so acceptance is provable — an order references the exact version row the customer
accepted, so the original text stays recoverable even after the team edits its terms.

**There is no PATCH and no DELETE.** Editing terms means publishing a new version.

### `GET /terms`

Full history, **newest version first**.

```json
{
  "data": {
    "client_form_terms_versions": {
      "byClientId": {
        "12": {
          "id": 12,
          "version_number": 2,
          "content": { "blocks": [{ "type": "p", "text": "v2" }] },
          "is_active": true,
          "created_at": "2026-07-24T11:47:46.690316+00:00",
          "created_by_user_id": null
        },
        "11": {
          "id": 11,
          "version_number": 1,
          "content": { "blocks": [{ "type": "p", "text": "v1" }] },
          "is_active": false,
          "created_at": "2026-07-24T11:47:46.687648+00:00",
          "created_by_user_id": null
        }
      },
      "allIds": ["12", "11"]
    }
  },
  "warnings": []
}
```

Remember: keys here are **stringified `id`s**, not `client_id`s.

Optional filter: `GET /terms?is_active=true` returns just the live version.

| Field | Type | Notes |
|---|---|---|
| `id` | `int` | what the client form sends back as `accepted_terms_version_id` |
| `version_number` | `int` | starts at 1, increments per publish |
| `content` | JSON object or array | rich-text document — shape is yours to define |
| `is_active` | `bool` | exactly one `true` per team |
| `created_at` | ISO 8601 UTC | |
| `created_by_user_id` | `int \| null` | |

### `PUT /terms` — publish a new version

**Request**
```json
{ "fields": { "content": { "blocks": [{ "type": "p", "text": "Delivery terms…" }] } } }
```

**Response**
```json
{ "data": { "id": 11, "version_number": 1 }, "warnings": [] }
```

`content` must be a **non-empty JSON object or array**. `null`, `{}`, `[]`, a bare string, or a
number all return **410**. Treat it as an editor document (same role as
`message_template.template`) — the backend stores it verbatim and never inspects its internals.

---

## 3. Rules — ordered list

### `GET /rules`

Always ordered by `position` ascending.

```json
{
  "data": {
    "client_form_rules": {
      "byClientId": {
        "rule-tmp-1": {
          "id": 13,
          "client_id": "rule-tmp-1",
          "position": 1,
          "enabled": true,
          "title": "Check the box",
          "body": null,
          "icon": "box",
          "image_url": null
        }
      },
      "allIds": ["rule-tmp-1"]
    }
  },
  "warnings": []
}
```

| Field | Type | Notes |
|---|---|---|
| `id` | `int` | |
| `client_id` | `string` | map key |
| `position` | `int` | gapless, 0-based |
| `enabled` | `bool` | disabled rules are hidden from the public form |
| `title` | `string` | **required**, trimmed, non-empty |
| `body` | `string \| null` | long text |
| `icon` | `string \| null` | free-form key for your icon set |
| `image_url` | `string \| null` | |

Optional filter: `?enabled=true`.

### `PUT /rules` — create

```json
{
  "fields": [
    { "client_id": "rule-tmp-1", "title": "Check the box", "icon": "box" },
    { "client_id": "rule-tmp-2", "title": "Call ahead", "image_url": "https://cdn/x.png" }
  ]
}
```

**`position` is optional and normally omitted** — new rules append to the end automatically. Pass it
explicitly only to pin a slot; a collision returns **410**.

### `PATCH /rules` — update

```json
{ "target": { "target_id": 13, "fields": { "enabled": false, "title": "New title" } } }
```

`target_id` is the numeric `id` — not `client_id` (see the note above).

Response is an empty envelope: `{ "data": {}, "warnings": [] }`.

For multiple, use `targets` with an array. To move a single rule, prefer the reorder endpoint below —
patching `position` directly can collide with the row already holding that slot.

### `DELETE /rules`

```json
{ "target_ids": [13, 14] }
```

Response: `{ "data": {}, "warnings": [] }`.

Deleting leaves a gap in `position` (e.g. `0, 2`). That is harmless — ordering still works. Call
reorder afterwards if you want a compact sequence.

### `POST /rules/reorder`

```json
{ "ordered_ids": [14, 13, 12] }
```

Rewrites positions to `0, 1, 2` in the order given.

**`ordered_ids` must list every rule for the team exactly once.** A partial list, a duplicate, or an
empty array returns **410** — a partial rewrite would leave unlisted rows colliding on `position`.
So: send your full local list, not just the moved subset.

**Response** — the ids in their new order:
```json
{ "data": [14, 13, 12], "warnings": [] }
```

---

## 4. Media — ordered list per placement

### `GET /media`

Ordered by `placement`, then `position`.

```json
{
  "data": {
    "client_form_media": {
      "byClientId": {
        "m-card": {
          "id": 15,
          "client_id": "m-card",
          "placement": "carousel",
          "position": 0,
          "enabled": true,
          "url": "https://cdn/a.png",
          "storage_key": null,
          "alt_text": "promo art",
          "link_url": "https://shop/deal",
          "title": "Spring offer",
          "description": "Free delivery on orders over 500 kr."
        },
        "m-bare": {
          "id": 16,
          "client_id": "m-bare",
          "placement": "sidebar_left",
          "position": 0,
          "enabled": true,
          "url": "https://cdn/logo.png",
          "storage_key": null,
          "alt_text": null,
          "link_url": null,
          "title": null,
          "description": null
        }
      },
      "allIds": ["m-card", "m-bare"]
    }
  },
  "warnings": []
}
```

| Field | Type | Notes |
|---|---|---|
| `id` | `int` | |
| `client_id` | `string` | map key |
| `placement` | enum | see the enum table above |
| `position` | `int` | 0-based **within its placement** |
| `enabled` | `bool` | |
| `url` | `string` | **required**, trimmed, non-empty |
| `storage_key` | `string \| null` | **always `null` today** — reserved for a future upload pipeline. Ignore it. |
| `alt_text` | `string \| null` | accessibility text for the image — **not** a visible caption |
| `link_url` | `string \| null` | wrap the image in a link |
| `title` | `string \| null` | visible heading |
| `description` | `string \| null` | visible body copy, long-form |

A media item is therefore an image-primary **card**: the image is the only required part, and
`title` / `description` / `link_url` are optional layers on top. A plain banner leaves all three
`null`; a promo card fills them in.

`alt_text` and `title` are distinct on purpose — `alt_text` is the `alt` attribute (screen readers,
broken-image fallback), `title` is rendered copy. Don't collapse them.

Optional filters: `?placement=carousel`, `?enabled=true`. An unknown `placement` value returns **410**.

### `PUT /media` — create

```json
{
  "fields": [
    {
      "client_id": "m-card",
      "placement": "carousel",
      "url": "https://cdn/a.png",
      "alt_text": "promo art",
      "link_url": "https://shop/deal",
      "title": "Spring offer",
      "description": "Free delivery on orders over 500 kr."
    },
    { "client_id": "m-bare", "placement": "sidebar_left", "url": "https://cdn/logo.png" }
  ]
}
```

Only `placement` and `url` are required. The second entry above is a valid bare banner.

As with rules, omit `position` — it appends within the given placement. Two items in *different*
placements may share position `0`; two in the *same* placement may not.

There is no upload endpoint. `url` is whatever URL you supply.

### `PATCH /media` / `DELETE /media`

Same conventions as rules. Both return `{ "data": {}, "warnings": [] }`.

### `POST /media/reorder`

Scoped to **one placement** — `placement` is required alongside `ordered_ids`:

```json
{ "placement": "carousel", "ordered_ids": [14, 13] }
```

`ordered_ids` must list every media item **in that placement** exactly once.

**Response**: `{ "data": [14, 13], "warnings": [] }`

---

# Public Client Form

## `GET /public/client-form/<token>` — now returns `config`

No auth. The token identifies the order, and the team is resolved from it server-side.

**The response gains one new top-level key, `config`. Everything else is unchanged.**

```json
{
  "order_scalar_id": 101,
  "reference_number": "REF-101",
  "external_source": "shopify",
  "team_timezone": "Europe/Stockholm",
  "items": [{ "item_type": "Chair", "quantity": 2 }],
  "expires_at": "2026-04-11T12:00:00+00:00",
  "config": {
    "terms": {
      "version_id": 12,
      "version_number": 2,
      "content": { "blocks": [{ "type": "p", "text": "v2" }] }
    },
    "require_terms_acceptance": true,
    "rules": [
      { "id": 14, "position": 0, "title": "Call ahead", "body": null, "icon": null, "image_url": "https://cdn/x.png" },
      { "id": 13, "position": 1, "title": "Check the box", "body": null, "icon": "box", "image_url": null }
    ],
    "media": {
      "carousel": [
        {
          "id": 17,
          "position": 0,
          "url": "https://cdn/a.png",
          "alt_text": "promo art",
          "link_url": "https://shop/deal",
          "title": "Spring offer",
          "description": "Free delivery on orders over 500 kr."
        }
      ],
      "sidebar_left": [
        {
          "id": 18,
          "position": 0,
          "url": "https://cdn/logo.png",
          "alt_text": null,
          "link_url": null,
          "title": "Welcome",
          "description": "Confirm your details."
        }
      ]
    }
  }
}
```

### How the public projection differs from the admin shape

This is **not** the admin payload. It is a deliberately reduced view:

- Only **enabled** rules and media appear. Disabled rows are absent entirely.
- Internal fields are stripped — no `client_id`, no `storage_key`, no `enabled`, no `created_by_user_id`.
- `terms` carries only the **active** version, and the key is `version_id` (not `id`).
- `media` is an **object keyed by placement**, not a flat list. A placement with no enabled media is
  simply absent — iterate defensively.
- `rules` is a plain array already sorted by `position` — no `byClientId` map here.

### Empty and disabled states

| Situation | Result |
|---|---|
| Team never configured anything | `terms: null`, `rules: []`, `media: {}`, `require_terms_acceptance: false` |
| `terms_enabled: false` | `terms: null` even if versions exist |
| `terms_enabled: true` but nothing published | `terms: null` |
| `show_rules: false` | `rules: []` |
| `show_media: false` | `media: {}` |

`config` is always present with all four keys. Render every section conditionally.

### `require_terms_acceptance`

`true` only when **all three** hold: `terms_enabled`, `require_acceptance`, and a published active
version exists. When `true`, the form must not allow submission until the customer accepts — the
backend rejects the submission otherwise.

---

## `POST /public/client-form/<token>` — submitting acceptance

Send the `version_id` you received in `config.terms`:

```json
{
  "client_first_name": "Ada",
  "client_email": "ada@example.com",
  "accepted_terms_version_id": 12
}
```

`accepted_terms_version_id` must be an **integer** — the same value as `config.terms.version_id`.

The backend validates it against the team's currently-active version **before writing anything**. On
rejection the order is untouched and the token stays usable, so the customer can reload and resubmit.

| Situation | Result |
|---|---|
| Matches the active version | Accepted; order records the version and a timestamp |
| Omitted, and `require_terms_acceptance` is `false` | Accepted; no acceptance recorded |
| Omitted, and `require_terms_acceptance` is `true` | **410** — *"You must accept the terms and conditions to submit this form."* |
| Stale (the team republished after the form loaded), or from another team | **410** — *"The accepted terms version is no longer current. Reload the form and try again."* |
| Not an integer (e.g. `"12"`) | **410** — *"'accepted_terms_version_id' must be an integer."* |

**Handle the stale case explicitly.** A team can publish new terms while a customer has the form
open. Re-fetch `GET /public/client-form/<token>`, re-render the terms, and ask the customer to accept
again.

### Public form error statuses (unchanged)

These routes keep their own status mapping, distinct from the admin table above:

| Condition | HTTP | `code` |
|---|---|---|
| Token invalid | 404 | `token_invalid` |
| Token expired | 410 | `token_expired` |
| Already submitted | 409 | `token_already_used` |
| Validation failed (incl. terms) | 410 | `bad_request` |

Note the collision: **410 means both "token expired" and "validation failed"** on these routes.
Branch on `code`, not on the status.

---

# Admin Bootstrap

`GET /api_v2/bootstrap/` gains three keys so the admin app can hydrate without extra round-trips:

```json
{
  "client_form_settings": { ... },
  "client_form_rules":    { "byClientId": {...}, "allIds": [...] },
  "client_form_media":    { "byClientId": {...}, "allIds": [...] }
}
```

Same shapes as the dedicated endpoints. Terms versions are **not** in bootstrap — the history can grow
unbounded, so fetch `GET /terms` when the terms editor opens.

The **driver** bootstrap (`GET /api_v2/drivers/bootstrap`) is a separate service and is unchanged —
none of this reaches the driver app.

---

# Suggested Frontend Placement

Following `Front_end/AGENTS.md` layering:

```
features/client-form-config/
  domain/       mediaPlacement.ts          — mirror the placement enum; do not inline strings
  api/          clientFormConfig.api.ts    — one function per endpoint
  actions/      publishTerms.action.ts, reorderRules.action.ts, …
  flows/        clientFormConfig.flow.ts   — multi-step (e.g. publish + refetch history)
  controllers/  useClientFormConfigController.ts
  stores/       clientFormConfig.store.ts  — normalized by client_id, mirroring byClientId/allIds
```

Notes:

- Keep the raw `byClientId` / `allIds` DTO out of components — map to a view model in `api/` or `actions/`.
- The client-form app consumes `config` from its existing bootstrap call. It needs **no** new API
  client and must not import the admin feature — it is a separate app.
- Reorder is optimistic-friendly: it returns the new id order, and the server ordering is authoritative.
- On create, reconcile optimistic rows using the returned `client_id → id` map.

---

# Gotchas Checklist

- [ ] `GET /terms` keys are **stringified `id`s**; rules and media keys are `client_id`s
- [ ] `GET /settings` returns `"id": null` before first save — not an error, do not treat as missing
- [ ] Reorder requires the **complete** id list for that scope, not just moved items
- [ ] Media reorder additionally requires `placement`
- [ ] Omit `position` on create — it auto-appends
- [ ] Validation errors are HTTP **410**, permission **413**, not-found **414** (offset by +10)
- [ ] On the public form, 410 is ambiguous — branch on `code`
- [ ] `config.media` is keyed by placement and omits empty placements
- [ ] `config.terms` uses `version_id`, not `id`
- [ ] `storage_key` is always `null` — ignore it
- [ ] `alt_text` (a11y) and `title` (visible copy) are different fields — don't collapse them
- [ ] `PATCH` / `DELETE` `target_id` must be the **numeric `id`**, never `client_id`
- [ ] Handle the stale-terms rejection by re-fetching and re-prompting

---

# Known Backend Issue

**String `client_id` lookups are broken in `PATCH` / `DELETE` across the entire API.**

`Delivery_app_BK/services/queries/get_instance.py` line 23 queries the imported SQLAlchemy base
class `Model` instead of the `model` parameter (line 20 does it correctly):

```python
if isinstance(value, str):
    obj = db.session.query(Model).filter_by(client_id=value).one()   # should be `model`
```

Any `target_id` sent as a string raises `sqlalchemy.exc.ArgumentError`, surfacing as a **510**.
Verified against `MessageTemplate`, `Item`, `Order`, and `Costumer` — it is not specific to the
client-form tables and predates this feature.

Until it is fixed, send numeric `id`s everywhere. The `client_id → id` map returned by every create
response is there precisely so you can resolve them.
