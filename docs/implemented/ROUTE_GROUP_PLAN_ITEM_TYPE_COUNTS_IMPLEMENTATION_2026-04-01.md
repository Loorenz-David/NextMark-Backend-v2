# RoutePlan and RouteGroup item_type_counts - Implementation Summary

Date: 2026-04-01
Source plan archived from docs/under_development to docs/archive/ROUTE_GROUP_PLAN_ITEM_TYPE_COUNTS_2026-04-01.md.

## Scope completed

Implemented item_type_counts snapshots across:
- Order (foundation)
- RouteGroup
- RoutePlan

The RouteGroup/RoutePlan implementation followed the plan in:
- docs/archive/ROUTE_GROUP_PLAN_ITEM_TYPE_COUNTS_2026-04-01.md

## Database/model changes

Added model columns (JSONB with sqlite JSON variant):
- Delivery_app_BK/models/tables/order/order.py
  - item_type_counts
- Delivery_app_BK/models/tables/route_operations/route_plan/route_group.py
  - item_type_counts
- Delivery_app_BK/models/tables/route_operations/route_plan/route_plan.py
  - item_type_counts

Added migration:
- migrations/versions/r1t6y2u8i4o0_add_item_type_counts_to_route_plan_and_route_group.py
  - Adds item_type_counts to order, route_plan, route_group
  - Downgrade drops all three columns

## Aggregation behavior implemented

Order-level source snapshot:
- Delivery_app_BK/services/domain/order/recompute_order_totals.py
  - Computes order.item_type_counts from in-memory order.items
  - Aggregates by item_type using quantity (default 1)
  - Stores None when empty

Plan-level aggregation:
- Delivery_app_BK/services/domain/route_operations/plan/recompute_plan_totals.py
  - Existing scalar totals retained
  - Added merge of Order.item_type_counts across all orders in plan
  - Stores None when merged result is empty

Route-group-level aggregation:
- Delivery_app_BK/services/domain/route_operations/plan/recompute_route_group_totals.py
  - Zone-backed groups:
    - Keeps existing total_orders counting via OrderZoneAssignment
    - Adds per-zone merge of Order.item_type_counts
  - No-zone groups:
    - Keeps existing total_orders counting via Order.route_group_id
    - Adds merge of Order.item_type_counts for each no-zone group
  - Stores None when merged result is empty

## Serializer/API propagation

Added item_type_counts to outputs in:
- Delivery_app_BK/services/commands/route_plan/create_serializers.py
  - serialize_created_route_plan
  - serialize_created_route_group
- Delivery_app_BK/services/queries/route_plan/serialize_plan.py
  - serialize_plans stored totals block
  - _serialize_route_group_summary
- Delivery_app_BK/services/queries/route_plan/plan_types/serialize_route_group.py
  - _serialize_route_group_item
- Delivery_app_BK/services/queries/route_plan/route_groups/get_route_group.py
  - _serialize_route_group_detail
- Delivery_app_BK/services/queries/route_plan/route_groups/list_route_groups.py
  - _serialize_route_group

## Tests

Added:
- tests/unit/services/domain/plan/test_recompute_plan_totals.py
  - verifies merged item_type_counts
  - verifies None when no orders
  - verifies None-plan safety

Extended:
- tests/unit/services/domain/plan/test_recompute_route_group_totals.py
  - verifies zone and no-zone item_type_counts aggregation
  - keeps total_orders behavior checks
- tests/unit/services/queries/route_plan/test_serialize_plan.py
  - verifies plan and route-group item_type_counts serialization
- tests/unit/services/queries/route_plan/test_list_route_groups.py
  - verifies route-group item_type_counts in list response

Executed test command:
- .venv/bin/python -m pytest tests/unit/services/domain/plan/test_recompute_plan_totals.py tests/unit/services/domain/plan/test_recompute_route_group_totals.py tests/unit/services/queries/route_plan/test_serialize_plan.py tests/unit/services/queries/route_plan/test_list_route_groups.py

Result:
- 18 passed
