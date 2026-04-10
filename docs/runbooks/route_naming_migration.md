# Route Naming Canonicalization Runbook

## Status
Completed on 2026-03-27.

## Canonical Model
The backend uses canonical route naming across runtime code paths:
- `route_plan`
- `route_group`
- `route_plan_id`
- `route_group_id`

## Contracts
Route optimization endpoints require `route_group_id` in request JSON:
- `POST /api_v2/route_solutions/optimize`
- `PATCH /api_v2/route_solutions/optimize`
- `POST /api_v2/route_operations/optimize`
- `PATCH /api_v2/route_operations/optimize`

Example payload:

```json
{
  "route_group_id": 123,
  "route_end_strategy": "round_trip",
  "consider_traffic": true
}
```

## Validation Commands
Run from repo root:

```bash
.venv/bin/python -m pytest tests/unit --ignore=tests/unit/ai
.venv/bin/python -m pytest tests/unit/ai
PYTHONPATH="$PWD" .venv/bin/python scripts/report_route_naming_legacy_refs.py
```

## Archive Reference
Historical migration and handoff notes are archived under:
- `docs/archive/handoffs/`
