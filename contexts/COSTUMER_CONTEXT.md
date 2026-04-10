# Costumer Context Snapshot (Backend)

## Date
- 2026-03-02

## Purpose
This file snapshots the implemented Costumer backend context so work can resume after unrelated refactors.

## Implemented Scope
### Phase 2 services
- Added command layer under `Delivery_app_BK/services/commands/costumer/`:
  - `create_costumer.py`
  - `update_costumer.py`
  - `delete_costumer.py`
  - `resolve_or_create_costumer.py` (internal-only)
  - `__init__.py`
- Added query layer under `Delivery_app_BK/services/queries/costumer/`:
  - `list_costumers.py`
  - `find_costumers.py`
  - `serialize_costumer.py`
  - `costumer_stats.py`
  - `__init__.py`

### Request-layer refactor (SRP)
- Added request parsers under `Delivery_app_BK/services/requests/costumer/`:
  - `common.py`
  - `create_costumer.py`
  - `update_costumer.py`
  - `__init__.py`
- Exported parsers from `Delivery_app_BK/services/requests/__init__.py`.
- `create_costumer` and `update_costumer` now consume parsed request objects.

### API routing
- Added plural v2 router:
  - `Delivery_app_BK/routers/api_v2/costumer.py`
- Registered in:
  - `Delivery_app_BK/routers/api_v2/__init__.py`
- Endpoints:
  - `GET /api_v2/costumers/`
  - `POST /api_v2/costumers/`
  - `PUT /api_v2/costumers/`
  - `DELETE /api_v2/costumers/`

### Client ID correction
Added `client_id` to new phase-1 tables and service flows:
- Model updates:
  - `models/tables/costumer/costumer.py`
  - `models/tables/costumer/costumer_address.py`
  - `models/tables/costumer/costumer_phone.py`
  - `models/tables/costumer/costumer_operating_hours.py`
  - `models/tables/order/order_delivery_window.py`
- Migration added:
  - `migrations/versions/9c1f7d2ab4e3_add_client_id_to_costumer_phase_tables.py`
  - Adds columns/indexes and backfills missing `client_id` values.

## Contract Notes
- Canonical-only separation preserved:
  - Costumer services do not mutate Order snapshot fields.
- `update_costumer` supports explicit delete arrays:
  - `delete_address_ids`
  - `delete_phone_ids`
- No implicit nested delete by omission.
- Default assignment supports explicit nested flags:
  - `addresses[].is_default`
  - `phones[].is_default_primary`
  - `phones[].is_default_secondary`
- Conflict rule enforced:
  - cannot combine `default_*_id` with corresponding nested default flag in same payload.

## Known Schema Note
- `costumer_operating_hours.open_time/close_time` are currently non-null in schema.
- For `is_closed=true`, request normalization persists deterministic placeholder times (`00:00`) and serializer exposes null open/close for closed rows.

## Validation Performed
- `python3 -m compileall` run on:
  - costumer command/query/request modules
  - updated models
  - migration files
- No syntax errors in compiled files.

## Pending / Next Suggested Backend Steps
1. Run migration in target environments:
   - `alembic upgrade head`
2. Add backend tests for:
   - nested default flags
   - conflict with `default_*_id`
   - explicit delete behavior
   - resolver email/phone matching
3. Optionally add `GET /costumers/<id>` route if UI needs detail endpoint (frontend API currently has a `getById` client method scaffolded).
4. Order-costumer DB hardening follow-up:
   - Backfill existing rows where `order.costumer_id IS NULL` using the same resolve/create policy.
   - Add an Alembic migration to alter `order.costumer_id` to `NOT NULL`.

## Resume Instruction
When resuming, load this file first and continue from "Pending / Next Suggested Backend Steps".
