# Analytics Data Layer: Current Structure

Last updated: 2026-03-25

## Purpose

This document describes the current analytics data layer used by the backend.

It is intended for:
- Fast technical catch-up after context loss
- New team onboarding
- Cross-team understanding of data flow and boundaries

Related deep-dive:
- AI statistics system and reasoning guide: [Delivery_app_BK/ai/docs/STATISTICS_SYSTEM.md](../../Delivery_app_BK/ai/docs/STATISTICS_SYSTEM.md)

## High-Level Architecture

The analytics layer is built as a two-level system:

1. Route snapshot facts (event-driven)
- One row per route solution
- Computed when route state changes (selected/completed)

2. Daily aggregate facts (scheduled)
- One row per team and local calendar day (global row)
- Future-ready support for per-zone daily rows

The AI layer reads these facts through query helpers and capability tools.

## Source Code Map

### Core analytics package
- [Delivery_app_BK/analytics/aggregators/route_aggregator.py](../../Delivery_app_BK/analytics/aggregators/route_aggregator.py)
- [Delivery_app_BK/analytics/aggregators/daily_aggregator.py](../../Delivery_app_BK/analytics/aggregators/daily_aggregator.py)
- [Delivery_app_BK/analytics/queries/get_route_metrics.py](../../Delivery_app_BK/analytics/queries/get_route_metrics.py)
- [Delivery_app_BK/analytics/queries/get_daily_metrics.py](../../Delivery_app_BK/analytics/queries/get_daily_metrics.py)
- [Delivery_app_BK/analytics/zone_attribution.py](../../Delivery_app_BK/analytics/zone_attribution.py)

### ORM models
- [Delivery_app_BK/models/tables/analytics/route_metrics_snapshot.py](../../Delivery_app_BK/models/tables/analytics/route_metrics_snapshot.py)
- [Delivery_app_BK/models/tables/analytics/analytics_daily_fact.py](../../Delivery_app_BK/models/tables/analytics/analytics_daily_fact.py)
- [Delivery_app_BK/models/__init__.py](../../Delivery_app_BK/models/__init__.py)

### Jobs and scheduling
- [Delivery_app_BK/services/infra/jobs/tasks/analytics.py](../../Delivery_app_BK/services/infra/jobs/tasks/analytics.py)
- [redis_scheduler.py](../../redis_scheduler.py)
- [Delivery_app_BK/services/commands/plan/local_delivery/route_solution/select_route_solution.py](../../Delivery_app_BK/services/commands/plan/local_delivery/route_solution/select_route_solution.py)
- [Delivery_app_BK/services/commands/plan/local_delivery/route_solution/mark_route_solution_actual_end_time.py](../../Delivery_app_BK/services/commands/plan/local_delivery/route_solution/mark_route_solution_actual_end_time.py)

### AI capability and tools
- [Delivery_app_BK/ai/capabilities/analytics.py](../../Delivery_app_BK/ai/capabilities/analytics.py)
- [Delivery_app_BK/ai/capabilities/registry.py](../../Delivery_app_BK/ai/capabilities/registry.py)
- [Delivery_app_BK/ai/tools/analytics_tools.py](../../Delivery_app_BK/ai/tools/analytics_tools.py)
- [Delivery_app_BK/ai/prompts/analytics_execute_prompt.py](../../Delivery_app_BK/ai/prompts/analytics_execute_prompt.py)
- [Delivery_app_BK/routers/api_v2/ai.py](../../Delivery_app_BK/routers/api_v2/ai.py)

### Schema evolution and bootstrap
- [migrations/versions/a7n3c5e9d2f1_add_analytics_fact_tables.py](../../migrations/versions/a7n3c5e9d2f1_add_analytics_fact_tables.py)
- [scripts/backfill_analytics.py](../../scripts/backfill_analytics.py)

## Data Model

### analytics_route_metrics_snapshot

Grain:
- One row per route_solution_id

Main metrics:
- Stop punctuality counts (on-time, early, late)
- Delay metrics (average and max seconds)
- Route efficiency totals (distance, travel time, service time)
- Derived rates (on_time_rate, delay_rate)
- team_id and optional zone_id

Write semantics:
- Upsert by route_solution_id
- Existing row is overwritten to keep backfills and recomputations idempotent

### analytics_daily_fact

Grain:
- Global: one row per (team_id, date) where zone_id is null
- Zoned: one row per (team_id, date, zone_id) where zone_id is not null

Main metrics:
- Order totals and completion metrics
- Route totals and delay aggregates
- Distance and travel totals

Index strategy:
- Partial unique index for global rows
- Partial unique index for zoned rows
- Query index on team/date/zone

## Runtime Flow

### Route-level path (near real-time)

1. A route solution is selected or receives an actual end time.
2. Command handler enqueues compute_route_metrics_job.
3. Job computes route metrics from route and stop timestamps.
4. Snapshot is upserted in analytics_route_metrics_snapshot.

This is wired in:
- [Delivery_app_BK/services/commands/plan/local_delivery/route_solution/select_route_solution.py](../../Delivery_app_BK/services/commands/plan/local_delivery/route_solution/select_route_solution.py)
- [Delivery_app_BK/services/commands/plan/local_delivery/route_solution/mark_route_solution_actual_end_time.py](../../Delivery_app_BK/services/commands/plan/local_delivery/route_solution/mark_route_solution_actual_end_time.py)

### Daily path (scheduled)

1. Redis scheduler runs aggregate_daily_metrics_job every 86400 seconds.
2. For each team, yesterday is aggregated in team-local timezone.
3. Global daily row (zone_id null) is persisted.
4. Zoned rows are also computed for any distinct non-null zone_ids seen in route snapshots.

Scheduler registration is in:
- [redis_scheduler.py](../../redis_scheduler.py)

Job implementation is in:
- [Delivery_app_BK/services/infra/jobs/tasks/analytics.py](../../Delivery_app_BK/services/infra/jobs/tasks/analytics.py)

### Execution path (queues and workers)

Both analytics job types run through Redis Queue (RQ) on the default queue.

Route snapshot jobs:
1. Route command handlers enqueue compute_route_metrics_job with queue_key="default".
2. The default worker consumes the job from the default queue.
3. The worker executes compute_route_metrics_job and writes/updates analytics_route_metrics_snapshot.

Daily aggregation jobs:
1. redis_scheduler.py registers aggregate_daily_metrics_job as a periodic job.
2. The scheduler targets queue_name=queue_names.default.
3. The default worker consumes and executes aggregate_daily_metrics_job, which writes/updates analytics_daily_fact.

Execution references:
- [Delivery_app_BK/services/infra/jobs/queues.py](../../Delivery_app_BK/services/infra/jobs/queues.py)
- [redis_worker_default.py](../../redis_worker_default.py)
- [redis_scheduler.py](../../redis_scheduler.py)
- [Delivery_app_BK/services/infra/jobs/tasks/analytics.py](../../Delivery_app_BK/services/infra/jobs/tasks/analytics.py)
- [Delivery_app_BK/services/commands/plan/local_delivery/route_solution/select_route_solution.py](../../Delivery_app_BK/services/commands/plan/local_delivery/route_solution/select_route_solution.py)
- [Delivery_app_BK/services/commands/plan/local_delivery/route_solution/mark_route_solution_actual_end_time.py](../../Delivery_app_BK/services/commands/plan/local_delivery/route_solution/mark_route_solution_actual_end_time.py)

## Timezone Rules

Daily aggregation is team-timezone aware:
- Local day boundaries are built using team IANA timezone
- Boundaries are converted to UTC for database filtering
- Invalid timezone falls back to UTC

Implementation:
- [Delivery_app_BK/analytics/aggregators/daily_aggregator.py](../../Delivery_app_BK/analytics/aggregators/daily_aggregator.py)

## AI Integration

### New analytics capability

Available tools:
- get_daily_summary
- get_route_metrics_tool
- get_analytics_snapshot (legacy compatibility)
- get_zone_metrics (placeholder)
- get_zone_trends (placeholder)

Registration:
- [Delivery_app_BK/ai/capabilities/analytics.py](../../Delivery_app_BK/ai/capabilities/analytics.py)
- [Delivery_app_BK/ai/capabilities/registry.py](../../Delivery_app_BK/ai/capabilities/registry.py)

### Current routing note

Auto-routing hints in the API router now resolve analytics-like prompts to the analytics capability by default. Statistics remains available as a legacy/manual path for compatibility.

Reference:
- [Delivery_app_BK/routers/api_v2/ai.py](../../Delivery_app_BK/routers/api_v2/ai.py)

## Backfill and Recovery

Historical regeneration is supported via:
- [scripts/backfill_analytics.py](../../scripts/backfill_analytics.py)

Typical usage:
- python scripts/backfill_analytics.py --days-back 90

Recommended order after deploying schema changes:
1. Apply migration.
2. Run backfill.
3. Verify route snapshots and daily facts exist for active teams.

## Known Gaps and Planned Extensions

1. Zone attribution is currently a stub.
- Current behavior returns null zone_id.
- Planned implementation will map routes to zone polygons or majority-stop zone.

2. Zone analytics tools are placeholders.
- get_zone_metrics and get_zone_trends currently raise NotImplementedError.

3. Statistics compatibility path remains in parallel with analytics.
- Legacy statistics tooling is still present for backward compatibility while analytics capability becomes the default read-only insights path.

## Quick Verification Checklist

1. Confirm analytics capability registration
- .venv/bin/python -c "from Delivery_app_BK.ai.capabilities.registry import get_capability_profile; print(get_capability_profile('analytics').name)"

2. Confirm scheduler includes daily aggregation job
- inspect [redis_scheduler.py](../../redis_scheduler.py)

3. Confirm route hook enqueue points exist
- inspect [Delivery_app_BK/services/commands/plan/local_delivery/route_solution/select_route_solution.py](../../Delivery_app_BK/services/commands/plan/local_delivery/route_solution/select_route_solution.py)
- inspect [Delivery_app_BK/services/commands/plan/local_delivery/route_solution/mark_route_solution_actual_end_time.py](../../Delivery_app_BK/services/commands/plan/local_delivery/route_solution/mark_route_solution_actual_end_time.py)

4. Confirm migration file exists
- inspect [migrations/versions/a7n3c5e9d2f1_add_analytics_fact_tables.py](../../migrations/versions/a7n3c5e9d2f1_add_analytics_fact_tables.py)

5. Optionally run seed plus backfill for local validation
- use existing seed endpoint
- run backfill script for a short window
