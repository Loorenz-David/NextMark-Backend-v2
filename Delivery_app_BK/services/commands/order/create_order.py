from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy.exc import InvalidRequestError

from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.services.infra.events.builders.order import (
    build_client_form_submitted_event,
    build_order_created_event,
    mark_client_form_submission,
)
from Delivery_app_BK.models import (
    db,
    Item,
    ItemState,
    Order,
    OrderDeliveryWindow,
    OrderState,
    RoutePlan,
    RouteGroup,
    Team,
)

from ...context import ServiceContext
from ...requests.order.create_order import OrderCreateRequest, parse_create_order_request
from ..base.create_instance import create_instance
from ..costumer import CostumerResolutionInput, resolve_or_create_costumers
from ..utils import extract_fields
from .create_serializers import (
    serialize_created_items,
    serialize_created_order,
)
from Delivery_app_BK.services.infra.events.emiters.order import emit_order_events
from Delivery_app_BK.services.domain.plan.route_freshness import touch_route_freshness
from Delivery_app_BK.services.domain.order.plan_objective_labels import (
    resolve_effective_order_plan_objective,
)
from .plan_objectives import PlanObjectiveCreateResult, apply_order_plan_objective
from ...domain.order.delivery_windows import (
    resolve_order_delivery_windows_timezone,
    validate_and_normalize_delivery_windows,
    validate_same_local_day_delivery_windows,
)
from ...domain.order.order_scalar_id import reserve_order_scalar_ids
from .tracking.generate_tracking_identifiers import generate_tracking_identifiers
from ...domain.client_form.terms_acceptance import resolve_asserted_terms_version
from Delivery_app_BK.services.domain.order.recompute_order_totals import recompute_order_totals
from Delivery_app_BK.services.domain.plan.recompute_plan_totals import recompute_plan_totals


def create_order(
    ctx: ServiceContext,
    *,
    unplanned_discard_after: datetime | None = None,
):
    """
    `unplanned_discard_after` is the system-only opt-in for orders that are
    intentionally created without a plan objective: the objective stays
    unset instead of defaulting, and the order is marked for purge after that
    time unless someone plans it first.
    """
    ctx.set_relationship_map(
        {
            "team_id": Team,
            "order_state_id": OrderState,
            "delivery_plan_id": RoutePlan,
            "route_group_id": RouteGroup,
            "item_state_id": ItemState,
        }
    )

    order_requests: list[OrderCreateRequest] = [
        parse_create_order_request(field_set) for field_set in extract_fields(ctx)
    ]
    if unplanned_discard_after is not None and any(
        request.delivery_plan_id is not None for request in order_requests
    ):
        raise ValidationFailed("An unplanned order cannot be created into a plan.")

    pending_events: list[dict] = []
    created_bundles: list[dict] = []
    touched_route_plans: dict[int, RoutePlan] = {}

    def _apply() -> None:
        team_timezone = resolve_order_delivery_windows_timezone(ctx)
        resolved_costumers = resolve_or_create_costumers(
            ctx,
            [
                CostumerResolutionInput(
                    costumer_id=request.costumer.costumer_id if request.costumer else None,
                    costumer_client_id=request.costumer.client_id if request.costumer else None,
                    first_name=(
                        request.costumer.first_name
                        if request.costumer and request.costumer.first_name is not None
                        else request.fields.get("client_first_name")
                    ),
                    last_name=(
                        request.costumer.last_name
                        if request.costumer and request.costumer.last_name is not None
                        else request.fields.get("client_last_name")
                    ),
                    email=(
                        request.costumer.email
                        if request.costumer and request.costumer.email is not None
                        else request.fields.get("client_email")
                    ),
                    primary_phone=(
                        request.costumer.primary_phone
                        if request.costumer and request.costumer.primary_phone is not None
                        else request.fields.get("client_primary_phone")
                    ),
                    address=(
                        request.costumer.address
                        if request.costumer and request.costumer.address is not None
                        else request.fields.get("client_address")
                    ),
                )
                for request in order_requests
            ],
        )
        if len(resolved_costumers) != len(order_requests):
            raise ValidationFailed("Failed to resolve costumers for all orders.")
        route_plans_by_id = _load_route_plans_by_id(
            ctx,
            [
                request.delivery_plan_id
                for request in order_requests
                if request.delivery_plan_id is not None
            ],
        )
        order_instances: list[Order] = []
        item_instances: list[Item] = []
        extra_instances: list[object] = []
        post_flush_actions: list[Callable[[], None]] = []
        items_by_order_client_id: dict[str, list[Item]] = defaultdict(list)
        submission_source_by_client_id: dict[str, str] = {}
        plan_objective_results_by_order_client_id: dict[str, PlanObjectiveCreateResult] = {}
        allocated_scalar_ids = reserve_order_scalar_ids(ctx, len(order_requests))

        for order_request, resolved_costumer, order_scalar_id in zip(
            order_requests,
            resolved_costumers,
            allocated_scalar_ids,
        ):
            order_fields = dict(order_request.fields)
            order_fields["order_scalar_id"] = order_scalar_id
            normalized_windows = None
            if order_request.delivery_windows is not None:
                normalized_windows = validate_and_normalize_delivery_windows(
                    order_request.delivery_windows,
                )
                validate_same_local_day_delivery_windows(
                    normalized_windows,
                    team_timezone=team_timezone,
                )
            route_plan = (
                route_plans_by_id.get(order_request.delivery_plan_id)
                if order_request.delivery_plan_id is not None
                else None
            )
            if unplanned_discard_after is not None:
                order_fields["order_plan_objective"] = None
            elif not order_fields.get("order_plan_objective"):
                # An order joining a plan inherits that plan's domain. Only an
                # unassigned order falls back to the default.
                order_fields["order_plan_objective"] = resolve_effective_order_plan_objective(
                    route_plan.plan_type if route_plan is not None else None,
                    fallback="local_delivery",
                )
            resolved_route_plan_id = None
            if route_plan:
                resolved_route_plan_id = route_plan.id
            order_fields.pop("delivery_plan_id", None)

            # The customer accepted at the counter, on the in-store device; the
            # order recording it only exists now. Validated against the team's
            # active version rather than trusted, then stamped with the time the
            # order carries the acceptance from.
            accepted_terms = resolve_asserted_terms_version(
                ctx.team_id,
                order_fields.pop("accepted_terms_version_id", None),
            )

            order_instance: Order = create_instance(ctx, Order, order_fields)
            if unplanned_discard_after is not None:
                order_instance.discard_after = unplanned_discard_after
            if accepted_terms is not None:
                order_instance.accepted_terms_version_id = accepted_terms.id
                order_instance.terms_accepted_at = datetime.now(timezone.utc)
            order_instance.costumer_id = resolved_costumer.id
            if order_instance.costumer_id is None:
                raise ValidationFailed("Order must belong to a costumer.")
            if resolved_route_plan_id is not None:
                order_instance.route_plan_id = resolved_route_plan_id
                order_instance.route_plan = route_plan
                if route_plan is not None:
                    touched_route_plans[route_plan.id] = route_plan
            if order_request.submission_source is not None:
                order_instance.client_form_submitted_at = datetime.now(timezone.utc)
                submission_source_by_client_id[order_instance.client_id] = (
                    order_request.submission_source
                )
            order_instances.append(order_instance)

            if normalized_windows is not None:
                for window in normalized_windows:
                    order_instance.delivery_windows.append(
                        OrderDeliveryWindow(
                            team_id=ctx.team_id,
                            client_id=window.client_id,
                            start_at=window.start_at,
                            end_at=window.end_at,
                            window_type=window.window_type,
                        )
                    )
            
            for item_request in order_request.items:
                item_instance: Item = create_instance(ctx, Item, dict(item_request.fields))
                order_instance.items.append(item_instance)
                item_instances.append(item_instance)
                items_by_order_client_id[order_instance.client_id].append(item_instance)

            if order_request.items:
                order_instance.items_updated_at = datetime.now(timezone.utc)
                recompute_order_totals(order_instance)

            if route_plan is not None:
                recompute_plan_totals(route_plan)

            if route_plan:
                objective_result = apply_order_plan_objective(
                    ctx=ctx,
                    order_instance=order_instance,
                    route_plan=route_plan,
                )
                extra_instances.extend(objective_result.instances)
                post_flush_actions.extend(objective_result.post_flush_actions)
                plan_objective_results_by_order_client_id[order_instance.client_id] = (
                    objective_result
                )

        if order_instances:
            db.session.add_all(order_instances)
        if item_instances:
            db.session.add_all(item_instances)
        if extra_instances:
            db.session.add_all(extra_instances)

        db.session.flush()

        # Generate identifiers after the initial flush so the database primary
        # key is available if the scalar order ID is missing.
        for order_instance in order_instances:
            if order_instance.tracking_token_hash is None:
                generate_tracking_identifiers(order_instance)

        for action in post_flush_actions:
            action()
        if post_flush_actions:
            db.session.flush()

        for route_plan in touched_route_plans.values():
            touch_route_freshness(route_plan)
        if touched_route_plans:
            db.session.flush()

        for order_instance in order_instances:
            submission_source = submission_source_by_client_id.get(order_instance.client_id)
            pending_events.extend(
                _build_order_creation_events(
                    order_instance,
                    submission_source=submission_source,
                    relayed_by_user_id=ctx.user_id if submission_source else None,
                )
            )
            bundle = {"order": serialize_created_order(order_instance)}

            created_items = items_by_order_client_id.get(order_instance.client_id) or []
            if created_items:
                bundle["items"] = serialize_created_items(created_items)

            objective_result = plan_objective_results_by_order_client_id.get(
                order_instance.client_id
            )
            if objective_result:
                bundle.update(objective_result.serialize_bundle())

            created_bundles.append(bundle)

    try:
        with db.session.begin():
            _apply()
    except InvalidRequestError as exc:
        if "already begun" not in str(exc).lower():
            raise
        _apply()

    if pending_events:
        emit_order_events(ctx, pending_events)

    plan_totals = [
        {
            "id": plan.id,
            "total_weight": plan.total_weight_g,
            "total_volume": plan.total_volume_cm3,
            "total_items": plan.total_item_count,
            "total_orders": plan.total_orders,
        }
        for plan in touched_route_plans.values()
        if plan.id is not None
    ]
    return {"created": created_bundles, "plan_totals": plan_totals}


def _build_order_creation_events(
    order_instance: Order,
    *,
    submission_source: str | None = None,
    relayed_by_user_id: int | None = None,
) -> list[dict]:
    """The staff member creates the order. Only when the customer filled the
    form on a linked device is there also a client-form submission, and that
    one is the customer's."""
    events = [build_order_created_event(order_instance)]
    if submission_source is not None:
        events.append(
            mark_client_form_submission(
                build_client_form_submitted_event(order_instance),
                submission_source=submission_source,
                relayed_by_user_id=relayed_by_user_id,
            )
        )
    return events


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
    plans = query.all()

    plans_by_id = {plan.id: plan for plan in plans}
    missing_ids = [plan_id for plan_id in deduped_plan_ids if plan_id not in plans_by_id]
    if missing_ids:
        raise NotFound(f"Delivery plans not found: {missing_ids}")

    return plans_by_id
