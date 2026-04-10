from __future__ import annotations

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import InvalidRequestError, NoInspectionAvailable
from sqlalchemy.orm.exc import NoResultFound

from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.models import (
    CaseChat,
    Order,
    OrderCase,
    OrderZoneAssignment,
    RouteGroup,
    RoutePlan,
    RouteSolution,
    RouteSolutionStop,
    db,
)
from Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.plan_sync import (
    build_incremental_route_sync_action,
)
from Delivery_app_BK.services.commands.route_plan.local_delivery.route_solution.stops import (
    remove_orders_stops_for_local_delivery,
)
from Delivery_app_BK.services.infra.events.builders.order import (
    build_delivery_rescheduled_event,
    build_route_plan_changed_event,
)
from Delivery_app_BK.services.infra.events.emiters.order import emit_order_events
from Delivery_app_BK.services.queries.route_solutions.serialize_route_solutions import (
    serialize_route_solution,
)
from Delivery_app_BK.services.domain.route_operations.plan.route_freshness import touch_route_freshness
from Delivery_app_BK.services.domain.route_operations.plan.recompute_plan_totals import recompute_plan_totals
from Delivery_app_BK.services.domain.route_operations.plan.recompute_route_group_totals import (
    recompute_route_group_totals,
)
from Delivery_app_BK.services.domain.state_transitions.order_count_engine import (
    recompute_plan_order_counts,
    recompute_route_group_order_counts,
)
from Delivery_app_BK.services.domain.state_transitions.plan_state_engine import (
    apply_plan_state,
    maybe_auto_complete_plan,
    maybe_sync_plan_state_from_groups,
)
from Delivery_app_BK.services.domain.state_transitions.route_group_state_engine import (
    maybe_sync_route_group_state,
)
from Delivery_app_BK.services.domain.state_transitions.order_move_rules import compute_destination_move_result, OrderMoveResult
from Delivery_app_BK.services.domain.order.order_case_states import OrderCaseState
from Delivery_app_BK.services.utils import model_requires_team, require_team_id

from ...context import ServiceContext
from ...queries.get_instance import get_instance
from .create_serializers import serialize_created_order, serialize_created_order_stops
from .plan_changes import (
    PlanChangeResult,
    apply_order_plan_change,
    build_plan_change_apply_context,
)


def apply_orders_route_plan_change(
    ctx: ServiceContext,
    order_ids: int | list[int],
    plan_id: int,
    destination_route_group_id: int | None = None,
) -> dict:
    normalized_order_ids = _normalize_order_ids(order_ids)
    if not normalized_order_ids:
        return {
            "updated": [],
            "pending_events": [],
        }

    new_plan = _resolve_plan_instance(ctx, plan_id)
    orders_by_target_id = _resolve_orders_for_update(ctx, normalized_order_ids)

    old_plan_ids: set[int] = set()
    changed_orders: list[Order] = []
    old_plan_id_by_order_id: dict[int, int | None] = {}
    old_route_group_id_by_order_id: dict[int, int | None] = {}

    for target_id in normalized_order_ids:
        order_instance = orders_by_target_id[target_id]
        old_plan_id = _get_order_route_plan_id(order_instance)
        old_route_group_id = _get_order_route_group_id(order_instance)

        if old_plan_id == new_plan.id:
            if destination_route_group_id is None or old_route_group_id == destination_route_group_id:
                ctx.set_warning(
                    f"Order: {target_id}. Is already in the destination selection provided on update"
                )
                continue

        if old_plan_id is not None:
            old_plan_ids.add(old_plan_id)

        old_plan_id_by_order_id[order_instance.id] = old_plan_id
        old_route_group_id_by_order_id[order_instance.id] = old_route_group_id
        changed_orders.append(order_instance)

    if not changed_orders:
        return {
            "updated": [],
            "pending_events": [],
        }

    old_plans_by_id = _load_route_plans_by_id(ctx, list(old_plan_ids))
    route_groups_for_new_plan = _load_route_groups_for_plan(ctx, new_plan.id)
    destination_route_group_id_by_order_id = _resolve_destination_route_group_ids(
        ctx=ctx,
        changed_orders=changed_orders,
        old_plan_id_by_order_id=old_plan_id_by_order_id,
        route_groups_for_new_plan=route_groups_for_new_plan,
        destination_route_group_id=destination_route_group_id,
        new_plan_id=new_plan.id,
    )
    affected_route_groups = _resolve_affected_route_groups(
        ctx=ctx,
        old_route_group_id_by_order_id=old_route_group_id_by_order_id,
        destination_route_group_id_by_order_id=destination_route_group_id_by_order_id,
    )

    relevant_plan_ids = set(old_plan_ids)
    relevant_plan_ids.add(new_plan.id)
    apply_context = build_plan_change_apply_context(
        ctx=ctx,
        plan_ids=list(relevant_plan_ids),
    )
    apply_context.source_route_group_id_by_order_id = {
        order_id: route_group_id
        for order_id, route_group_id in old_route_group_id_by_order_id.items()
        if route_group_id is not None
    }
    apply_context.destination_route_group_id_by_order_id = destination_route_group_id_by_order_id
    old_local_delivery_batch = _prepare_old_local_delivery_batch_changes(
        ctx=ctx,
        apply_context=apply_context,
        old_plans_by_id=old_plans_by_id,
        old_plan_id_by_order_id=old_plan_id_by_order_id,
        old_route_group_id_by_order_id=old_route_group_id_by_order_id,
    )
    batched_old_local_delivery_order_ids: set[int] = old_local_delivery_batch["order_ids"]

    pending_events: list[dict] = []
    extra_instances: list[object] = list(old_local_delivery_batch["instances"])
    post_flush_actions = list(old_local_delivery_batch["post_flush_actions"])
    plan_change_result_by_order_id: dict[int, PlanChangeResult] = {}

    for target_id in normalized_order_ids:
        order_instance = orders_by_target_id[target_id]
        if order_instance.id not in old_plan_id_by_order_id:
            continue

        old_plan_id = old_plan_id_by_order_id[order_instance.id]
        old_plan = old_plans_by_id.get(old_plan_id) if old_plan_id else None
        old_plan_for_apply = (
            None
            if order_instance.id in batched_old_local_delivery_order_ids
            else old_plan
        )

        _set_order_route_plan_id(order_instance, new_plan.id)
        _set_order_route_group_id(
            order_instance,
            destination_route_group_id_by_order_id.get(order_instance.id),
        )
        order_instance.order_plan_objective = "local_delivery"

        change_result = apply_order_plan_change(
            ctx=ctx,
            order_instance=order_instance,
            old_plan=old_plan_for_apply,
            new_plan=new_plan,
            apply_context=apply_context,
        )
        plan_change_result_by_order_id[order_instance.id] = change_result
        extra_instances.extend(change_result.instances)
        post_flush_actions.extend(change_result.post_flush_actions)

        if old_plan is not None and (
            (getattr(old_plan, "start_date", None), getattr(old_plan, "end_date", None))
            != (getattr(new_plan, "start_date", None), getattr(new_plan, "end_date", None))
        ):
            pending_events.append(
                build_delivery_rescheduled_event(
                    order_instance,
                    old_plan_start=getattr(old_plan, "start_date", None),
                    old_plan_end=getattr(old_plan, "end_date", None),
                    new_plan_start=getattr(new_plan, "start_date", None),
                    new_plan_end=getattr(new_plan, "end_date", None),
                    reason="plan_move_date_changed",
                )
            )

        pending_events.append(
            build_route_plan_changed_event(order_instance, old_plan_id, new_plan)
        )

    if extra_instances:
        sanitized_extra_instances = _sanitize_instances_for_session(extra_instances)
        if sanitized_extra_instances:
            db.session.add_all(sanitized_extra_instances)

    db.session.flush()

    for action in post_flush_actions:
        action()
    if post_flush_actions:
        db.session.flush()

    plans_to_touch = {plan.id: plan for plan in [new_plan, *old_plans_by_id.values()]}
    for route_plan in plans_to_touch.values():
        touch_route_freshness(route_plan)
    if plans_to_touch:
        db.session.flush()

    # Recompute denormalized plan totals for all affected plans.
    _plans_to_recompute = {new_plan.id: new_plan}
    _plans_to_recompute.update(old_plans_by_id)
    for plan in _plans_to_recompute.values():
        recompute_plan_totals(plan)
        recompute_route_group_totals(plan)
    if _plans_to_recompute:
        db.session.flush()

    # Recompute per-state order counts, apply state heritage, then check auto-complete.
    for plan in _plans_to_recompute.values():
        recompute_plan_order_counts(plan)
    case_message = (ctx.incoming_data or {}).get("case_message") if ctx.incoming_data else None
    _apply_move_state_heritage(
        ctx=ctx,
        changed_orders=changed_orders,
        new_plan=new_plan,
        plans_to_recompute=_plans_to_recompute,
        affected_route_groups=affected_route_groups,
        case_message=case_message,
    )
    db.session.flush()

    old_local_delivery_bundle = _serialize_old_local_delivery_batch_bundle(
        updated_stops=old_local_delivery_batch["updated_stops"],
        synced_stops=old_local_delivery_batch["synced_stops"],
        updated_route_solutions=old_local_delivery_batch["updated_route_solutions"],
        synced_route_solutions=old_local_delivery_batch["synced_route_solutions"],
    )
    state_changes_bundle = _build_state_changes_bundle(
        route_groups=affected_route_groups,
        route_plans=list(_plans_to_recompute.values()),
    )
    old_local_delivery_bundle_attached = False
    plan_totals_attached = False
    state_changes_attached = False

    updated_bundles: list[dict] = []
    for target_id in normalized_order_ids:
        order_instance = orders_by_target_id[target_id]
        if order_instance.id not in old_plan_id_by_order_id:
            continue

        bundle = {
            "order": serialize_created_order(order_instance),
        }
        change_result = plan_change_result_by_order_id.get(order_instance.id)
        if change_result:
            bundle.update(change_result.serialize_bundle())
        if old_local_delivery_bundle and not old_local_delivery_bundle_attached:
            bundle.update(old_local_delivery_bundle)
            old_local_delivery_bundle_attached = True
        if not plan_totals_attached:
            bundle["plan_totals"] = [
                {
                    "id": plan.id,
                    "total_weight": plan.total_weight_g,
                    "total_volume": plan.total_volume_cm3,
                    "total_items": plan.total_item_count,
                    "total_orders": plan.total_orders,
                }
                for plan in _plans_to_recompute.values()
                if plan.id is not None
            ]
            plan_totals_attached = True
        if not state_changes_attached:
            bundle["state_changes"] = state_changes_bundle
            state_changes_attached = True

        updated_bundles.append(bundle)

    return {
        "updated": updated_bundles,
        "pending_events": pending_events,
    }


def _prepare_old_local_delivery_batch_changes(
    *,
    ctx: ServiceContext,
    apply_context,
    old_plans_by_id: dict[int, RoutePlan],
    old_plan_id_by_order_id: dict[int, int | None],
    old_route_group_id_by_order_id: dict[int, int | None],
) -> dict:
    order_ids_by_old_route_group_id: dict[int, list[int]] = {}
    batched_order_ids: set[int] = set()

    for order_id, old_plan_id in old_plan_id_by_order_id.items():
        old_route_group_id = old_route_group_id_by_order_id.get(order_id)
        if old_plan_id is None or old_route_group_id is None:
            continue
        if old_plan_id not in old_plans_by_id:
            continue
        order_ids_by_old_route_group_id.setdefault(old_route_group_id, []).append(order_id)
        batched_order_ids.add(order_id)

    if not order_ids_by_old_route_group_id:
        return {
            "instances": [],
            "post_flush_actions": [],
            "order_ids": set(),
            "updated_stops": [],
            "synced_stops": [],
            "updated_route_solutions": [],
            "synced_route_solutions": [],
        }

    updated_stops: list[RouteSolutionStop] = []
    synced_stops: list[RouteSolutionStop] = []
    updated_route_solutions: list[RouteSolution] = []
    synced_route_solutions: list[RouteSolution] = []
    starts_by_route_id: dict[int, int] = {}

    for old_route_group_id, order_ids in order_ids_by_old_route_group_id.items():
        (
            removed_updated_stops,
            removed_updated_route_solutions,
            removed_starts_by_route_id,
        ) = remove_orders_stops_for_local_delivery(order_ids, old_route_group_id)

        updated_stops.extend(removed_updated_stops)
        updated_route_solutions.extend(removed_updated_route_solutions)
        starts_by_route_id = _merge_start_positions(starts_by_route_id, removed_starts_by_route_id)

    post_flush_actions = []
    if starts_by_route_id:
        post_flush_actions.append(
            build_incremental_route_sync_action(
                ctx=ctx,
                starts_by_route_id=starts_by_route_id,
                route_solutions_by_id=_build_route_solutions_by_id_from_context(apply_context),
                synced_stops=synced_stops,
                changed_route_solutions=synced_route_solutions,
            )
        )

    instances: list[object] = []
    instances.extend(updated_stops)
    instances.extend(updated_route_solutions)

    return {
        "instances": instances,
        "post_flush_actions": post_flush_actions,
        "order_ids": batched_order_ids,
        "updated_stops": updated_stops,
        "synced_stops": synced_stops,
        "updated_route_solutions": updated_route_solutions,
        "synced_route_solutions": synced_route_solutions,
    }


def _merge_start_positions(
    base: dict[int, int],
    incoming: dict[int, int],
) -> dict[int, int]:
    if not incoming:
        return base

    merged = dict(base)
    for route_id, start_position in incoming.items():
        current = merged.get(route_id)
        merged[route_id] = (
            start_position if current is None else min(current, start_position)
        )
    return merged


def _build_route_solutions_by_id_from_context(apply_context) -> dict[int, RouteSolution]:
    route_solutions_by_id: dict[int, RouteSolution] = {}
    for route_solutions in apply_context.route_solutions_by_route_group_id.values():
        for route_solution in route_solutions:
            route_id = getattr(route_solution, "id", None)
            if route_id is None:
                continue
            route_solutions_by_id[route_id] = route_solution
    return route_solutions_by_id


def _serialize_old_local_delivery_batch_bundle(
    *,
    updated_stops: list[RouteSolutionStop],
    synced_stops: list[RouteSolutionStop],
    updated_route_solutions: list[RouteSolution],
    synced_route_solutions: list[RouteSolution],
) -> dict:
    stops = _dedupe_stops_for_bundle(list(updated_stops or []) + list(synced_stops or []))
    route_solutions = _dedupe_route_solutions_for_bundle(
        list(updated_route_solutions or []) + list(synced_route_solutions or [])
    )

    bundle: dict = {}
    if stops:
        bundle["order_stops"] = serialize_created_order_stops(stops)
    if route_solutions:
        bundle["route_solution"] = [
            serialize_route_solution(route_solution) for route_solution in route_solutions
        ]
    return bundle


def _build_state_changes_bundle(
    *,
    route_groups: list[RouteGroup],
    route_plans: list[RoutePlan],
) -> dict:
    route_group_rows: list[dict] = []
    seen_route_group_ids: set[int] = set()
    for route_group in route_groups or []:
        route_group_id = getattr(route_group, "id", None)
        if route_group_id is None or route_group_id in seen_route_group_ids:
            continue
        seen_route_group_ids.add(route_group_id)
        route_group_rows.append(
            {
                "id": route_group_id,
                "state_id": route_group.state_id,
                "total_orders": route_group.total_orders,
                "order_state_counts": route_group.order_state_counts,
                "route_plan_id": route_group.route_plan_id,
                "zone_id": route_group.zone_id,
            }
        )

    route_plan_rows: list[dict] = []
    seen_route_plan_ids: set[int] = set()
    for route_plan in route_plans or []:
        route_plan_id = getattr(route_plan, "id", None)
        if route_plan_id is None or route_plan_id in seen_route_plan_ids:
            continue
        seen_route_plan_ids.add(route_plan_id)
        route_plan_rows.append(
            {
                "id": route_plan_id,
                "state_id": route_plan.state_id,
                "total_orders": route_plan.total_orders,
            }
        )

    route_group_rows.sort(key=lambda row: row["id"])
    route_plan_rows.sort(key=lambda row: row["id"])

    return {
        "route_groups": route_group_rows,
        "route_plans": route_plan_rows,
    }


def _dedupe_stops_for_bundle(stops: list[RouteSolutionStop]) -> list[RouteSolutionStop]:
    deduped: list[RouteSolutionStop] = []
    seen_keys: set[tuple[str, str]] = set()

    for stop in stops:
        stop_id = getattr(stop, "id", None)
        client_id = getattr(stop, "client_id", None)
        key = (
            "id" if stop_id is not None else "client_id",
            str(stop_id if stop_id is not None else client_id),
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(stop)

    return sorted(
        deduped,
        key=lambda stop: (
            stop.stop_order if getattr(stop, "stop_order", None) is not None else 10**9,
            getattr(stop, "id", 10**9),
            getattr(stop, "client_id", ""),
        ),
    )


def _dedupe_route_solutions_for_bundle(
    route_solutions: list[RouteSolution],
) -> list[RouteSolution]:
    deduped: list[RouteSolution] = []
    seen_ids: set[int] = set()

    for route_solution in route_solutions:
        route_id = getattr(route_solution, "id", None)
        if route_id is None or route_id in seen_ids:
            continue
        seen_ids.add(route_id)
        deduped.append(route_solution)
    return deduped


def _sanitize_instances_for_session(instances: list[object]) -> list[object]:
    sanitized: list[object] = []
    seen_instance_ids: set[int] = set()

    for instance in instances:
        if instance is None:
            continue
        instance_ref = id(instance)
        if instance_ref in seen_instance_ids:
            continue
        seen_instance_ids.add(instance_ref)

        try:
            inspected = sa_inspect(instance)
            if getattr(inspected, "deleted", False):
                continue
        except NoInspectionAvailable:
            pass

        sanitized.append(instance)

    return sanitized


def _apply_move_state_heritage(
    *,
    ctx: ServiceContext,
    changed_orders: list,
    new_plan,
    plans_to_recompute: dict,
    affected_route_groups: list[RouteGroup],
    case_message: str | None,
) -> None:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    for order in changed_orders:
        result = compute_destination_move_result(order, new_plan, now)
        if result.new_order_state_id is not None:
            order.order_state_id = result.new_order_state_id
        if result.new_plan_state_id is not None:
            apply_plan_state(new_plan, result.new_plan_state_id)
        if result.should_create_case:
            _create_move_case(ctx, order, result, case_message)

    for plan in plans_to_recompute.values():
        recompute_plan_order_counts(plan)

    for route_group in affected_route_groups:
        recompute_route_group_order_counts(route_group)

    for plan in plans_to_recompute.values():
        maybe_auto_complete_plan(plan)

    for route_group in affected_route_groups:
        maybe_sync_route_group_state(route_group)

    for plan in plans_to_recompute.values():
        maybe_sync_plan_state_from_groups(plan)


def _create_move_case(
    ctx: ServiceContext,
    order,
    result: OrderMoveResult,
    user_message: str | None,
) -> None:
    full_text = result.case_predefined_text or ""
    if user_message:
        full_text = f"{full_text}\n\n{user_message}".strip()

    user_id = None
    if ctx.identity:
        user_id = ctx.identity.get("user_id")

    case = OrderCase(
        team_id=order.team_id,
        order_id=order.id,
        state=OrderCaseState.OPEN.value,
        label="Order moved to ready plan",
        created_by=user_id,
    )
    db.session.add(case)
    db.session.flush()

    if full_text:
        chat = CaseChat(
            team_id=order.team_id,
            order_case_id=case.id,
            message=full_text,
            user_id=user_id,
            user_name="System",
        )
        db.session.add(chat)


def update_orders_route_plan(
    ctx: ServiceContext,
    order_ids: int | list[int],
    plan_id: int | None,
    destination_route_group_id: int | None = None,
) -> dict:
    try:
        with db.session.begin():
            if plan_id is None:
                outcome = apply_orders_route_plan_unassign(ctx, order_ids)
            else:
                outcome = apply_orders_route_plan_change(
                    ctx,
                    order_ids,
                    plan_id,
                    destination_route_group_id=destination_route_group_id,
                )
    except InvalidRequestError as exc:
        if "already begun" not in str(exc).lower():
            raise
        if plan_id is None:
            outcome = apply_orders_route_plan_unassign(ctx, order_ids)
        else:
            outcome = apply_orders_route_plan_change(
                ctx,
                order_ids,
                plan_id,
                destination_route_group_id=destination_route_group_id,
            )

    pending_events = outcome.get("pending_events") or []
    if pending_events:
        emit_order_events(ctx, pending_events)

    return {"updated": outcome.get("updated") or []}


def update_order_route_plan(
    ctx: ServiceContext,
    order_id: int,
    plan_id: int,
    destination_route_group_id: int | None = None,
) -> dict:
    return update_orders_route_plan(
        ctx,
        order_id,
        plan_id,
        destination_route_group_id=destination_route_group_id,
    )


def unassign_order_route_plan(
    ctx: ServiceContext,
    order_id: int,
) -> dict:
    return update_orders_route_plan(ctx, order_id, None)


def apply_orders_route_plan_unassign(
    ctx: ServiceContext,
    order_ids: int | list[int],
) -> dict:
    normalized_order_ids = _normalize_order_ids(order_ids)
    if not normalized_order_ids:
        return {
            "updated": [],
            "pending_events": [],
        }

    orders_by_target_id = _resolve_orders_for_update(ctx, normalized_order_ids)

    old_plan_ids: set[int] = set()
    changed_orders: list[Order] = []
    old_plan_id_by_order_id: dict[int, int | None] = {}
    old_route_group_id_by_order_id: dict[int, int | None] = {}

    for target_id in normalized_order_ids:
        order_instance = orders_by_target_id[target_id]
        old_plan_id = _get_order_route_plan_id(order_instance)
        if old_plan_id is None:
            ctx.set_warning(
                f"Order: {target_id}. Is already unassigned from any delivery plan"
            )
            continue

        old_plan_ids.add(old_plan_id)
        old_plan_id_by_order_id[order_instance.id] = old_plan_id
        old_route_group_id_by_order_id[order_instance.id] = _get_order_route_group_id(
            order_instance
        )
        changed_orders.append(order_instance)

    if not changed_orders:
        return {
            "updated": [],
            "pending_events": [],
        }

    old_plans_by_id = _load_route_plans_by_id(ctx, list(old_plan_ids))
    apply_context = build_plan_change_apply_context(
        ctx=ctx,
        plan_ids=list(old_plan_ids),
    )
    apply_context.source_route_group_id_by_order_id = {
        order_id: route_group_id
        for order_id, route_group_id in old_route_group_id_by_order_id.items()
        if route_group_id is not None
    }
    old_local_delivery_batch = _prepare_old_local_delivery_batch_changes(
        ctx=ctx,
        apply_context=apply_context,
        old_plans_by_id=old_plans_by_id,
        old_plan_id_by_order_id=old_plan_id_by_order_id,
        old_route_group_id_by_order_id=old_route_group_id_by_order_id,
    )
    batched_old_local_delivery_order_ids: set[int] = old_local_delivery_batch["order_ids"]

    pending_events: list[dict] = []
    extra_instances: list[object] = list(old_local_delivery_batch["instances"])
    post_flush_actions = list(old_local_delivery_batch["post_flush_actions"])
    plan_change_result_by_order_id: dict[int, PlanChangeResult] = {}

    for target_id in normalized_order_ids:
        order_instance = orders_by_target_id[target_id]
        if order_instance.id not in old_plan_id_by_order_id:
            continue

        old_plan_id = old_plan_id_by_order_id[order_instance.id]
        old_plan = old_plans_by_id.get(old_plan_id) if old_plan_id else None
        old_plan_for_apply = (
            None
            if order_instance.id in batched_old_local_delivery_order_ids
            else old_plan
        )

        _set_order_route_plan_id(order_instance, None)
        _set_order_route_group_id(order_instance, None)
        order_instance.order_plan_objective = None

        change_result = apply_order_plan_change(
            ctx=ctx,
            order_instance=order_instance,
            old_plan=old_plan_for_apply,
            new_plan=None,
            apply_context=apply_context,
        )
        plan_change_result_by_order_id[order_instance.id] = change_result
        extra_instances.extend(change_result.instances)
        post_flush_actions.extend(change_result.post_flush_actions)

        pending_events.append(
            build_route_plan_changed_event(order_instance, old_plan_id, None)
        )

    if extra_instances:
        sanitized_extra_instances = _sanitize_instances_for_session(extra_instances)
        if sanitized_extra_instances:
            db.session.add_all(sanitized_extra_instances)

    db.session.flush()

    for action in post_flush_actions:
        action()
    if post_flush_actions:
        db.session.flush()

    plans_to_touch = {plan.id: plan for plan in old_plans_by_id.values()}
    for route_plan in plans_to_touch.values():
        touch_route_freshness(route_plan)
    if plans_to_touch:
        db.session.flush()

    for plan in old_plans_by_id.values():
        recompute_plan_totals(plan)
        recompute_route_group_totals(plan)
        recompute_plan_order_counts(plan)
        maybe_auto_complete_plan(plan)
        for route_group in (plan.route_groups or []):
            recompute_route_group_order_counts(route_group)
            maybe_sync_route_group_state(route_group)
        maybe_sync_plan_state_from_groups(plan)
    if old_plans_by_id:
        db.session.flush()

    old_local_delivery_bundle = _serialize_old_local_delivery_batch_bundle(
        updated_stops=old_local_delivery_batch["updated_stops"],
        synced_stops=old_local_delivery_batch["synced_stops"],
        updated_route_solutions=old_local_delivery_batch["updated_route_solutions"],
        synced_route_solutions=old_local_delivery_batch["synced_route_solutions"],
    )
    state_changes_bundle = _build_state_changes_bundle(
        route_groups=[
            route_group
            for plan in old_plans_by_id.values()
            for route_group in (plan.route_groups or [])
        ],
        route_plans=list(old_plans_by_id.values()),
    )
    old_local_delivery_bundle_attached = False
    plan_totals_attached = False
    state_changes_attached = False

    updated_bundles: list[dict] = []
    for target_id in normalized_order_ids:
        order_instance = orders_by_target_id[target_id]
        if order_instance.id not in old_plan_id_by_order_id:
            continue

        bundle = {
            "order": serialize_created_order(order_instance),
        }
        change_result = plan_change_result_by_order_id.get(order_instance.id)
        if change_result:
            bundle.update(change_result.serialize_bundle())
        if old_local_delivery_bundle and not old_local_delivery_bundle_attached:
            bundle.update(old_local_delivery_bundle)
            old_local_delivery_bundle_attached = True
        if not plan_totals_attached:
            bundle["plan_totals"] = [
                {
                    "id": plan.id,
                    "total_weight": plan.total_weight_g,
                    "total_volume": plan.total_volume_cm3,
                    "total_items": plan.total_item_count,
                    "total_orders": plan.total_orders,
                }
                for plan in old_plans_by_id.values()
                if plan.id is not None
            ]
            plan_totals_attached = True
        if not state_changes_attached:
            bundle["state_changes"] = state_changes_bundle
            state_changes_attached = True

        updated_bundles.append(bundle)

    return {
        "updated": updated_bundles,
        "pending_events": pending_events,
    }



def _normalize_order_ids(order_ids: int | list[int]) -> list[int]:
    if isinstance(order_ids, int) and not isinstance(order_ids, bool):
        return [order_ids]

    if not isinstance(order_ids, list):
        raise ValidationFailed("order_ids must be provided as an integer or list.")

    deduped_order_ids: list[int] = []
    seen: set[int] = set()
    for order_id in order_ids:
        if isinstance(order_id, bool) or not isinstance(order_id, int):
            raise ValidationFailed("Each order id must be an integer.")
        if order_id in seen:
            continue
        seen.add(order_id)
        deduped_order_ids.append(order_id)

    return deduped_order_ids


def _load_route_groups_for_plan(
    ctx: ServiceContext,
    route_plan_id: int,
) -> list[RouteGroup]:
    query = db.session.query(RouteGroup).filter(RouteGroup.route_plan_id == route_plan_id)
    if ctx.team_id:
        query = query.filter(RouteGroup.team_id == ctx.team_id)
    route_groups = query.order_by(RouteGroup.id.asc()).all()
    if not route_groups:
        raise ValidationFailed("Route group not found for destination route plan.")
    return route_groups


def _load_zone_assignments_by_order_id(
    order_ids: list[int],
) -> dict[int, OrderZoneAssignment]:
    if not order_ids:
        return {}

    rows = (
        db.session.query(OrderZoneAssignment)
        .filter(OrderZoneAssignment.order_id.in_(order_ids))
        .all()
    )
    return {row.order_id: row for row in rows}


def _resolve_destination_route_group_ids(
    *,
    ctx: ServiceContext,
    changed_orders: list[Order],
    old_plan_id_by_order_id: dict[int, int | None],
    route_groups_for_new_plan: list[RouteGroup],
    destination_route_group_id: int | None,
    new_plan_id: int,
) -> dict[int, int]:
    if destination_route_group_id is not None:
        if not any(group.id == destination_route_group_id for group in route_groups_for_new_plan):
            raise ValidationFailed("route_group_id must belong to the destination route plan.")
        return {order.id: destination_route_group_id for order in changed_orders}

    if len(route_groups_for_new_plan) == 1:
        only_group_id = route_groups_for_new_plan[0].id
        return {order.id: only_group_id for order in changed_orders}

    zone_assignments_by_order_id = _load_zone_assignments_by_order_id(
        [order.id for order in changed_orders if order.id is not None]
    )
    route_group_id_by_zone_id = {
        group.zone_id: group.id
        for group in route_groups_for_new_plan
        if group.zone_id is not None
    }
    no_zone_group_id = next(
        (group.id for group in route_groups_for_new_plan if group.zone_id is None),
        None,
    )

    destination_by_order_id: dict[int, int] = {}
    for order in changed_orders:
        if old_plan_id_by_order_id.get(order.id) == new_plan_id:
            current_route_group_id = _get_order_route_group_id(order)
            if current_route_group_id is not None:
                destination_by_order_id[order.id] = current_route_group_id
                continue

        assignment = zone_assignments_by_order_id.get(order.id)
        zone_id = None
        if assignment is not None and not assignment.is_unassigned:
            zone_id = assignment.zone_id

        mapped_route_group_id = route_group_id_by_zone_id.get(zone_id)
        if mapped_route_group_id is None:
            if no_zone_group_id is not None:
                mapped_route_group_id = no_zone_group_id
            else:
                raise ValidationFailed(
                    f"Unable to infer destination route_group_id for order {order.id}."
                )
        destination_by_order_id[order.id] = mapped_route_group_id

    return destination_by_order_id


def _resolve_affected_route_groups(
    *,
    ctx: ServiceContext,
    old_route_group_id_by_order_id: dict[int, int | None],
    destination_route_group_id_by_order_id: dict[int, int],
) -> list[RouteGroup]:
    affected_ids = {
        route_group_id
        for route_group_id in old_route_group_id_by_order_id.values()
        if route_group_id is not None
    }
    affected_ids.update(destination_route_group_id_by_order_id.values())
    if not affected_ids:
        return []

    query = db.session.query(RouteGroup).filter(RouteGroup.id.in_(affected_ids))
    if ctx.team_id:
        query = query.filter(RouteGroup.team_id == ctx.team_id)
    return query.all()


def _resolve_plan_instance(ctx: ServiceContext, plan_id: int) -> RoutePlan:
    if isinstance(plan_id, bool) or not isinstance(plan_id, int):
        raise ValidationFailed("plan_id must be provided as an integer.")
    try:
        return get_instance(ctx, RoutePlan, plan_id)
    except NoResultFound as exc:
        raise NotFound(str(exc)) from exc


def _resolve_orders_for_update(
    ctx: ServiceContext,
    order_ids: list[int],
) -> dict[int, Order]:
    if not order_ids:
        return {}

    deduped_order_ids = list(dict.fromkeys(order_ids))
    orders_by_id: dict[int, Order] = {}

    team_id = None
    if model_requires_team(Order) and ctx.check_team_id:
        team_id = require_team_id(ctx)

    query = db.session.query(Order).filter(Order.id.in_(deduped_order_ids)).with_for_update()
    if team_id is not None:
        query = query.filter(Order.team_id == team_id)
    for order in query.all():
        orders_by_id[order.id] = order

    missing_ids = [order_id for order_id in deduped_order_ids if order_id not in orders_by_id]
    if missing_ids:
        raise NotFound(f"Orders not found: {missing_ids}")

    return {order_id: orders_by_id[order_id] for order_id in deduped_order_ids}


def _load_route_plans_by_id(
    ctx: ServiceContext,
    plan_ids: list[int],
) -> dict[int, RoutePlan]:
    deduped_plan_ids = list(dict.fromkeys(plan_ids))
    if not deduped_plan_ids:
        return {}

    query = db.session.query(RoutePlan).filter(RoutePlan.id.in_(deduped_plan_ids))
    if ctx.team_id:
        query = query.filter(RoutePlan.team_id == ctx.team_id)

    return {plan.id: plan for plan in query.all()}


def _get_order_route_plan_id(order: Order) -> int | None:
    return getattr(order, "route_plan_id", None)


def _set_order_route_plan_id(order: Order, route_plan_id: int | None) -> None:
    order.route_plan_id = route_plan_id


def _get_order_route_group_id(order: Order) -> int | None:
    return getattr(order, "route_group_id", None)


def _set_order_route_group_id(order: Order, route_group_id: int | None) -> None:
    order.route_group_id = route_group_id
