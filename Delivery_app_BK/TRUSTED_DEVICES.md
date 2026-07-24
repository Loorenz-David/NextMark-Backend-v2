# Trusted Devices — Multi-User Authentication & Instant Account Switching

> Authoritative contract for the trusted-device capability. Backend engineers
> and frontend engineers both build against this document.

---

## 1. What this is

A **trusted device** is an explicitly registered browser/installation that is
allowed to hold authentication for **several permitted users at once**. On a
trusted device, one user signs in normally and the backend returns an
independent authentication bundle (access + refresh + socket tokens) for
**every** user assigned to that device. The frontend can then switch the
active user **locally and instantly** — no new login request per switch.

This applies **only** to trusted devices. Ordinary (untrusted) login is
unchanged and fully backward compatible.

### Core rule

> The **backend owns** the device→user assignments. The frontend may choose
> which returned user is active, but it can never create, extend, or bypass
> the list of users authorized for a device.

---

## 2. Domain model

Three team-scoped tables (all under `models/tables/trusted_device/`):

| Table | Purpose |
|---|---|
| `trusted_device` | One registered device. Holds `client_id` (`tdv_…`), `name`, `device_secret_hash` (never the raw secret), `is_active`, `last_used_at`, `revoked_at/by`, `team_id`. |
| `trusted_device_user` | Device↔user assignment. `UNIQUE(trusted_device_id, user_id)`; independently revocable via `is_active` + `revoked_at/by`. |
| `trusted_device_event` | Security audit log. Never stores secrets, passwords, or tokens. |

A user is included in a device's login bundle only when **all** hold:
`device is active` **and** `assignment is active` **and** the user can build a
valid session for the requested `app_scope`.

> **Account-status note:** the `User` model has no `is_active`/disabled flag.
> "Eligible to authenticate" therefore means the user can resolve a workspace
> for the requested `app_scope` (the existing login rule). There is no
> account-disable switch to honor today; if one is added later, add it to the
> eligibility check in `build_trusted_device_sessions`.

---

## 3. Device credentials (how a device identifies itself)

A trusted device presents two values as **HTTP headers** (never in the JSON
body, query string, or URL):

```
X-Trusted-Device-Id:     tdv_01abc…      (public client_id)
X-Trusted-Device-Secret: <opaque secret> (shown once at registration/rotation)
```

The secret is generated with a CSPRNG, and only its **HMAC-SHA256 hash
(peppered)** is stored. The raw secret is returned exactly once (registration
or rotation) and must never be logged.

The backend distinguishes these cases and never leaks which is which to an
unauthorized caller:
- **no** device headers → ordinary login;
- **invalid** device headers (bad id/secret, inactive, revoked) → generic
  `Trusted-device authentication failed.` (HTTP 410). No fallback — presenting
  broken device credentials is a hard failure;
- **valid** device headers, initiating user **assigned** → trusted-device flow;
- **valid** device headers, initiating user **not assigned** → ordinary
  single-user login.

> **Enrollment is a capability, not a whitelist.** Registering a device does not
> restrict who may sign in from that browser. Any user with correct credentials
> logs in normally there; assignment is what additionally grants the multi-user
> bundle and instant switching. This matters because the frontend attaches the
> device headers to *every* request once enrolled — an unassigned user would
> otherwise be permanently locked out of that installation.

---

## 4. Login — request & the two response shapes

### Request (unchanged)

`POST /api_v2/auths/login`
```json
{ "email": "u@x.com", "password": "…", "app_scope": "driver", "time_zone": "Europe/Stockholm" }
```
Device credentials travel in headers, **not** this body.

All responses use the standard envelope: `{ "data": <payload>, "warnings": [] }`.
Everything below is the `data` object. **Branch on `authentication_mode`.**

### 4a. Ordinary login (no device headers, or a valid device the user isn't assigned to)

```jsonc
{
  "authentication_mode": "single_user",   // NEW discriminator
  "access_token": "…",
  "refresh_token": "…",
  "socket_token": "…",
  "user": { /* AuthenticatedUser — now includes client_id */ }
}
```
Byte-compatible with the old response except the added `authentication_mode`
and `user.client_id`. Existing clients that ignore unknown fields are unaffected.

### 4b. Trusted-device login (valid headers, initiating user assigned)

```jsonc
{
  "authentication_mode": "trusted_device",
  "trusted_device": { "client_id": "tdv_01…", "name": "Warehouse Front Desk" },
  "active_user_client_id": "user_01…",     // pick the active session by THIS
  "sessions": [
    {
      "user_client_id": "user_01…",
      "access_token": "…",
      "refresh_token": "…",
      "socket_token": "…",
      "user": { /* AuthenticatedUser */ }
    },
    { "user_client_id": "user_02…", "access_token": "…", "refresh_token": "…", "socket_token": "…", "user": {…} }
  ]
}
```

Guarantees the frontend can rely on:
- `sessions[0]` is the **initiating** user and `active_user_client_id ===
  sessions[0].user_client_id`. **Trust `active_user_client_id`, not array order.**
- Every session has its own access, refresh, socket token **and** a distinct
  `session_scope_id` (inside `user`). Never dedupe on `session_scope_id`.
- Excluded users (e.g. couldn't build a session for the scope, or over the
  per-device cap) don't appear in `sessions`; a top-level warning is emitted:
  ```json
  "warnings": [ { "code": "trusted_device_users_excluded", "count": 1 } ]
  ```
  Login still succeeds.
- Valid device + initiating user **not** assigned → an ordinary `single_user`
  response (§4a). Branch on `authentication_mode`: a device-enrolled client can
  still receive `single_user` and must store it as a plain session, **not**
  merge it into `sessionsByUserClientId`. Invalid device headers remain a hard
  failure (HTTP 410).

### `AuthenticatedUser` (the `user` object, both modes)

```jsonc
{
  "client_id": "user_01…",          // NEW — the stable map key
  "id": 12,
  "username": "David",
  "email": "david@example.com",
  "profile_picture": null,
  "app_scope": "driver",
  "session_scope_id": "e3b0…",      // UNIQUE per session
  "user_role_id": 4, "base_role_id": 2, "base_role": "admin",
  "current_workspace": "team", "has_team_workspace": true,
  "show_app_tutorial": false,
  "teamId": 21, "active_team_id": 21, "team_name": "North Team",
  "default_country_code": "SE", "default_city_key": "stockholm"
}
```

> **Key everything by `user.client_id`** (mirrored as `session.user_client_id`) —
> never by `id`, `email`, `username`, or array index.

---

## 5. Refresh — independent per user, revocation-aware

Each session refreshes with **its own** refresh token. Shapes unchanged:

```
POST /api_v2/auths/refresh_token          Authorization: Bearer <that user's refresh_token>
→ data: { "access_token": "…" }

POST /api_v2/auths/refresh_socket_token    Authorization: Bearer <that user's refresh_token>
→ data: { "socket_token": "…" }
```

Rules:
- Refreshing one user updates **only** that `user_client_id`'s context. Never
  overwrite other users' tokens.
- Trusted-device tokens carry `trusted_device_id` in their claims. On every
  refresh the backend re-checks that the device is still active/unrevoked and
  the user's assignment still active. If not → the refresh **fails** with
  `Trusted-device session is no longer valid.` (HTTP 410).

> **Revocation model (enforce-on-refresh).** There is no JWT blocklist, and
> refresh tokens live ~30 days. Access tokens live 1 hour. So a revoked device
> or removed user keeps a *currently valid access token* until it expires
> (≤ 1h), then loses access because the refresh is rejected. Treat that
> rejection as "drop **this** user's context," **not** "log everyone out."

---

## 6. Endpoints

Runtime (device-credential authenticated):

| Method | Path | Auth | Returns |
|---|---|---|---|
| POST | `/api_v2/auths/login` | headers optional | single_user or trusted_device payload |
| POST | `/api_v2/auths/refresh_token` | refresh JWT | `{ access_token }` |
| POST | `/api_v2/auths/refresh_socket_token` | refresh JWT | `{ socket_token }` |
| GET  | `/api_v2/auths/trusted-device/users` | device headers | device + assigned users (no tokens) |
| POST | `/api_v2/auths/trusted-device/sessions/refresh` | device headers + assigned-user access JWT | fresh `sessions` payload (same shape as 4b) |

Administration (**ADMIN role only**, team-scoped):

| Method | Path | Purpose |
|---|---|---|
| POST   | `/api_v2/auths/trusted-devices` | register device + assign users; returns secret **once** |
| GET    | `/api_v2/auths/trusted-devices` | list team devices (+ active user counts) |
| GET    | `/api_v2/auths/trusted-devices/{device_client_id}` | one device + assigned users |
| PATCH  | `/api_v2/auths/trusted-devices/{device_client_id}` | rename / enable / disable |
| DELETE | `/api_v2/auths/trusted-devices/{device_client_id}` | revoke device |
| POST   | `/api_v2/auths/trusted-devices/{device_client_id}/secret` | rotate secret; returns new secret **once** |
| POST   | `/api_v2/auths/trusted-devices/{device_client_id}/users` | assign a user (`{ "user_client_id": "user_…" }`) |
| DELETE | `/api_v2/auths/trusted-devices/{device_client_id}/users/{user_client_id}` | remove a user |

### `/trusted-device/users` response
```jsonc
{ "trusted_device": { "client_id": "tdv_…", "name": "…" },
  "users": [ { "id": 12, "client_id": "user_…", "username": "David", "profile_picture": null } ] }
```
Useful for rendering the user selector before/after login and after restart.
**Never returns tokens.**

### `/trusted-device/sessions/refresh`
Returns the **same shape as trusted-device login** (`§4b`). Use for app
startup, explicit resync, recovery from revoked refresh tokens, or after an
admin changes assignments. **Not** for every account switch. Reuse the login
parser for it.

### Registration
`POST /trusted-devices` body:
```json
{ "name": "Warehouse Front Desk", "user_client_ids": ["user_01…", "user_02…"] }
```
Response (secret shown once — store/display it immediately, it is
unrecoverable):
```json
{ "trusted_device": { "client_id": "tdv_01…", "name": "…", "is_active": true, … },
  "device_secret": "<one-time-secret>", "assigned_user_count": 2 }
```

---

## 7. Frontend contract

### 7.1 State shape

```ts
type AuthenticationContext = {
  accessToken: string;
  refreshToken: string;
  socketToken: string;
  user: AuthenticatedUser;   // includes client_id, session_scope_id, app_scope, team…
};

type TrustedDeviceAuthState = {
  mode: "trusted_device";
  trustedDevice: { clientId: string; name: string };
  activeUserClientId: string;                              // from active_user_client_id
  sessionsByUserClientId: Record<string, AuthenticationContext>;  // keyed by user.client_id
};
```
Build `sessionsByUserClientId` from the `sessions` array, keyed by
`user_client_id`. Set `activeUserClientId` from `active_user_client_id`.

### 7.2 Switching the active user (local, immediate)

```
1. ctx = sessionsByUserClientId[selectedUserClientId]   // must exist
2. activeUserClientId = selectedUserClientId
3. point the API client's access/refresh token source at ctx
4. point the socket client's socket token source at ctx (reconnect — see 7.3)
5. clear/namespace all previous-user-scoped app state (see 7.4)
6. reload user-specific data as needed
```

No backend call is required while the selected user's access token is valid.
If it has expired, the API client's normal refresh path uses **that user's**
refresh token to mint a new access token (one refresh request, then proceed) —
and updates **only** that user's context.

> This project's session layer already sits behind a single `SessionAccessor`
> (`getSession/setSession/clear/subscribe`) that the API client and socket
> client both read. The cheapest implementation makes the accessor hold the
> keyed collection + an active pointer and swap internally; the existing
> singleton API/socket clients then keep working without changes.

### 7.3 Sockets

Every user has a **separate** `socket_token`. On switch you must:
disconnect the previous user's socket → set the new user's socket token →
reconnect as the new user → drop the previous user's subscriptions. Do not
assume one shared socket identity for the device.

### 7.4 Data isolation (important)

Switching the auth token is **not** enough. Previous-user private data must not
remain visible. On switch, clear or namespace by active user: API/query
caches, profile, permissions, workspace state, notifications, socket
subscriptions, open task details, persisted form state, and any
IndexedDB/localStorage keyed by user. (This app's entity stores are global
singletons today; a token swap alone will leak user A's data into user B.)

### 7.5 Token storage — accepted tradeoff

The device holds renewable credentials (refresh tokens) for **every** assigned
user. **Decision for this project: persist the multi-user bundle in
`localStorage`** (extending the existing `beyo.driver.session` slot into
`{ sessionsByUserClientId, activeUserClientId }`). This is an explicit,
accepted tradeoff: it survives restarts but widens the blast radius of XSS,
malicious extensions, or local profile compromise. Keep the existing
per-app storage-key isolation (`beyo.driver.session` vs `beyo.admin.session`).

---

## 8. Configuration

Add to environment (see `config/default.py`):

| Setting | Default | Meaning |
|---|---|---|
| `TRUSTED_DEVICE_SECRET_PEPPER` | falls back to `JWT_SECRET_KEY` | server-side pepper mixed into every device-secret hash; set a dedicated value in production |
| `MAX_USERS_PER_DEVICE` | `25` | cap on sessions built per device login |

---

## 9. Audit & security invariants

Recorded in `trusted_device_event` (actor, device, target user, IP, user-agent,
result, timestamp): device registered/updated/revoked, secret rotated, user
assigned/removed, sessions resynced. **Never** written anywhere: raw password,
raw device secret, access/refresh/socket tokens, full Authorization header.

Enforced invariants:
- Admins only manage devices; management is scoped to the caller's team — one
  team can never read or mutate another team's devices or assignments.
- A frontend-selected user is honored only if the backend confirms the active
  device assignment; frontend-supplied ids can't bypass it.
- Revoked devices/removed users cannot obtain new bundles or refresh.
- An unassigned user signing in from an enrolled device gets **only their own**
  single-user session — never another assigned user's tokens.

---

## 10. Backend source map

- Models: `models/tables/trusted_device/`
- Device auth domain (hash/verify/resolve/assignment/refresh-check):
  `services/domain/auth/trusted_device.py`
- Token claims: `services/commands/auth/token_utils.py`
- Login + session builder: `services/commands/auth/login_user.py`,
  `build_trusted_device_sessions.py`
- Refresh revocation: `services/commands/auth/refresh_user_token.py`,
  `refresh_socket_token.py`
- Management commands: `services/commands/auth/{register,update,revoke,
  rotate_trusted_device_secret,assign_trusted_device_user,
  remove_trusted_device_user}.py`
- Runtime device endpoints: `services/commands/auth/{get_trusted_device_users,
  resync_trusted_device_sessions}.py`
- Queries: `services/queries/auth/{list_trusted_devices,get_trusted_device}.py`
- Audit writer: `services/commands/auth/trusted_device_audit.py`
- Request parsers: `services/requests/auth/trusted_device.py`
- Routes: `routers/api_v2/auth.py`
- Migrations: `migrations/versions/tdv1a2b3c4d5_*`, `tdv2b3c4d5e6f_*`
