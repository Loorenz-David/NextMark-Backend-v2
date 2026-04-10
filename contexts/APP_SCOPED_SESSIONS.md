# App-Scoped Sessions

This document explains the backend auth/session model used by `admin-app` and `driver-app`.

## Goal

The backend now supports concurrent sessions for different apps without forcing them to share one mutable global workspace.

This solves the old problem where:
- switching workspace in one app changed the user's active `team_id`
- the other app then became stale or invalid

## Core Concepts

There are now two separate concepts:

1. Durable user membership and identity
- stored on `User`
- includes:
  - `primals_team_id`
  - `primals_role_id`
  - `team_workspace_team_id`
  - `team_workspace_role_id`

2. Active app session context
- carried by JWT claims
- resolved per app
- includes:
  - `app_scope`
  - `session_scope_id`
  - `current_workspace`
  - `active_team_id`
  - `base_role`
  - `has_team_workspace`

## App Scopes

Supported app scopes:
- `admin`
- `driver`

They are required on login and preserved on refresh.

## Session Scope

Each login also gets a `session_scope_id`.

Purpose:
- lets concurrent app sessions stay independent
- refresh preserves the same `session_scope_id`
- workspace switching mints fresh tokens for the same app session, not for all apps

## Where App Workspace State Lives

Per-app workspace preference is persisted on `User`:
- `admin_app_current_workspace`
- `driver_app_current_workspace`

Current implementation only persists the workspace kind per app.
Active team and role are derived from durable membership state when tokens are minted.

## Token Source of Truth

Request-time active context must come from token claims, not directly from raw `User.team_id`.

`ServiceContext` now prefers:
- `active_team_id`
- `role_id`
- `app_scope`
- `session_scope_id`
- `current_workspace`

`ctx.team_id` resolves from `active_team_id` first.

## Workspace Resolution

Workspace resolution lives in:
- `Delivery_app_BK/services/domain/user/app_workspace.py`

Important helpers:
- `parse_app_scope(...)`
- `resolve_app_workspace_context(user, app_scope)`
- `ensure_app_workspace_state(user, app_scope)`
- `set_app_current_workspace(user, app_scope, workspace)`

Behavior:
- `admin-app` defaults to `personal`
- `driver-app` defaults to `team` when team workspace is available, otherwise `personal`
- `admin-app` team workspace is allowed only for team base roles:
  - `admin`
  - `assistant`

If a team role is `driver`, admin workspace is normalized back to `personal`.

## Auth Endpoints

Routes remain:
- `POST /api_v2/auths/login`
- `POST /api_v2/auths/refresh_token`
- `POST /api_v2/auths/refresh_socket_token`

Login payload now requires:
- `email`
- `password`
- `app_scope`
- optional `time_zone`

Refresh behavior:
- legacy refresh tokens without `app_scope` or `session_scope_id` are rejected
- client must re-login

## Router Access

App scope is now a security boundary.

Router guards are installed in:
- `Delivery_app_BK/routers/api_v2/__init__.py`
- `Delivery_app_BK/routers/utils/role_decorator.py`

Rules:
- admin routers require `app_scope == 'admin'`
- `drivers.py` requires `app_scope == 'driver'`
- existing role checks still apply after app-scope validation

## Workspace Switching

Driver workspace switch:
- `POST /api_v2/drivers/workspace/switch`

Admin workspace switch:
- `POST /api_v2/users/workspace/switch`

Payload:
- `{ "target_workspace": "personal" | "team" }`

Behavior:
- only that app's workspace is changed
- the same `session_scope_id` is preserved
- fresh tokens are returned for that app only

## Membership vs Active Context

These are intentionally different:

- membership answers:
  - "does this user belong to team X?"
- active context answers:
  - "which team/workspace is this app session currently operating under?"

Membership helpers still live under:
- `Delivery_app_BK/services/domain/user/team_membership.py`

Do not use raw `User.team_id` alone for membership-sensitive logic.

## Assistant App Guidance

If a new `assistant-app` is added later, follow the same pattern:

1. introduce a new `app_scope`
2. decide its allowed workspaces
3. add per-app workspace persistence if needed
4. mint tokens with:
   - `app_scope`
   - `session_scope_id`
   - `current_workspace`
   - `active_team_id`
5. protect its routers by app scope
6. keep its frontend session storage isolated from admin and driver

## Files To Read First

Backend entry points:
- `Delivery_app_BK/services/domain/user/app_workspace.py`
- `Delivery_app_BK/services/commands/auth/token_utils.py`
- `Delivery_app_BK/services/commands/auth/login_user.py`
- `Delivery_app_BK/services/commands/auth/refresh_user_token.py`
- `Delivery_app_BK/services/commands/user/switch_user_workspace.py`
- `Delivery_app_BK/services/commands/drivers/switch_driver_workspace.py`
- `Delivery_app_BK/routers/utils/role_decorator.py`
