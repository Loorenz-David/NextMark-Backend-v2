# AI Statistics System: Current and Intended Design

Last updated: 2026-03-25

## Why this document exists

This document explains:
- How statistics data is produced and stored over time
- How AI reads and reasons on top of that data
- What is currently implemented vs intended target behavior
- Practical examples for diagnosis and prediction

Use this file as the canonical reference for the AI statistics capability.

## System at a glance

There are two data sources used by AI statistics:

1. Live order-window analytics (order-centric)
- Computed at request time from orders in a timeframe
- Fast and simple baseline metrics
- No route dynamics by itself

2. Persisted analytics facts (route and daily)
- Route snapshots: per route solution
- Daily facts: per team/day and per team/day/zone
- Supports trend analysis, delay analysis, and zone comparisons

## Data pipeline

### A) Route snapshot pipeline (near real-time)

Trigger points:
- Route selection event
- Route actual end time update

Flow:
1. Command enqueues compute_route_metrics_job
2. Worker computes route metrics for the route_solution_id
3. Route snapshot upsert persists metrics in analytics_route_metrics_snapshot

Core metrics:
- total_stops, on_time_stops, early_stops, late_stops
- avg_delay_seconds, max_delay_seconds, on_time_rate, delay_rate
- total_distance_meters, total_travel_time_seconds, total_service_time_seconds
- zone_id and zone_version_id (derived from route stop assignments)

### B) Daily aggregation pipeline (scheduled)

Trigger point:
- aggregate_daily_metrics_job runs every 86400 seconds

Flow:
1. For each team, compute yesterday in team local timezone
2. Persist global row (zone_id = null)
3. Persist zoned rows from distinct (zone_id, zone_version_id) pairs present in route snapshots

Result table:
- analytics_daily_fact

## Zone attribution and versioning behavior

### Order assignment

Each order gets an OrderZoneAssignment with:
- zone_id
- zone_version_id
- assignment_type and assignment_method
- unassigned flags/reasons when no valid mapping exists

### Route attribution

Route zone attribution uses majority-stop strategy:
- Collect stop assignments from OrderZoneAssignment
- If one zone covers at least 60% of assigned stops, route gets that zone
- Otherwise, route remains unzoned (zone_id = null)

### Zone version evolution

When a zone version is activated:
1. Prior active version for same team/city is deactivated
2. Recent-window reassignment job runs (currently 7 days)
3. New and recent orders are re-evaluated for zone assignment under the active version

Historical rows retain old zone_version_id values, enabling before/after comparison across boundary changes.

## How AI consumes statistics

## Capability and tools

Statistics capability uses read-only tools:
- get_analytics_snapshot(timeframe)
- get_daily_summary(timeframe, zone_id)
- get_route_metrics_tool(days_back, zone_id)

Recommended query strategy for the planner:
1. Call get_analytics_snapshot first for baseline context
2. Call get_route_metrics_tool when question requires delay/route dynamics
3. Call get_daily_summary when question requires date-by-date or zone slices
4. Synthesize into evidence-based narrative with confidence and caveats

## Reasoning boundaries

Good at:
- Describing trends and operational shifts
- Comparing global vs zone slices
- Explaining where delay concentration appears
- Generating advisory recommendations

Not guaranteed to do:
- Causal certainty from observational data
- Reliable long-horizon forecasts without stronger modeling
- Automatic interventions (read-only capability by design)

## Current vs intended model

Current implementation:
- Route and daily facts are persisted and queryable
- Zone version id is threaded through daily zoned aggregation
- Statistics capability can access baseline + route + daily tools

Intended next level:
- Add explicit forecasting tool(s), not prompt-only prediction
- Add confidence calibration based on sample size and variance
- Add zone-shape quality metrics (e.g., reassignment churn, cross-zone leakage)
- Add change-point detection around zone_version activation dates

## Storage over time

What is retained:
- Route snapshot history in analytics_route_metrics_snapshot
- Daily fact history in analytics_daily_fact
- Zone assignment history by order in order_zone_assignment
- Zone genealogy through zone and zone_version

Operational implication:
- You can compare performance before/after zone boundary changes by filtering on zone_version_id and date windows
- You can isolate whether change came from demand mix, routing efficiency, or zone geometry shifts

## Worked examples

### Example 1: Why did completion drop this week?

Question:
- "Why did completion rate drop this week?"

Tool sequence:
1. get_analytics_snapshot(7d)
2. get_daily_summary(7d)
3. get_route_metrics_tool(days_back=7)

Interpretation pattern:
- If daily completion drops while delay_rate rises and route distance increases, likely routing pressure or corridor congestion rather than order intake anomaly.

### Example 2: Did new zone boundaries help?

Question:
- "Did the new city zoning improve operations?"

Analysis pattern:
1. Identify activation date and zone_version_id split
2. Compare two windows:
   - pre: 14 days before activation
   - post: 14 days after activation
3. For same zone slice(s), compare:
   - avg_delay_seconds
   - delay_rate
   - completion_rate

Interpretation caveat:
- Control for major demand shifts before claiming causal improvement.

### Example 3: Predict next-week risk hotspots

Question:
- "Where are we likely to miss SLAs next week?"

Practical heuristic (current state):
- Rank zones by recent weighted risk score:
  risk = 0.5 * normalized(delay_rate) + 0.3 * normalized(avg_delay_seconds) + 0.2 * normalized(volume)
- Highlight top zones as risk hotspots

Note:
- This is risk scoring guidance, not a trained forecasting model.

## File map

AI side:
- Delivery_app_BK/ai/capabilities/statistics/registry.py
- Delivery_app_BK/ai/prompts/statistics_execute_prompt.py
- Delivery_app_BK/ai/tools/analytics_tools.py

Analytics side:
- Delivery_app_BK/analytics/aggregators/route_aggregator.py
- Delivery_app_BK/analytics/aggregators/daily_aggregator.py
- Delivery_app_BK/services/infra/jobs/tasks/analytics.py
- Delivery_app_BK/analytics/zone_attribution.py

Zone side:
- Delivery_app_BK/zones/services/order_assignment_service.py
- Delivery_app_BK/services/infra/jobs/tasks/zones.py

## Maintenance rule

Update this file when any of the following changes:
- Statistics tool registry
- Aggregation semantics
- Zone attribution logic
- Scheduler cadence
- Prediction methodology or confidence policy
