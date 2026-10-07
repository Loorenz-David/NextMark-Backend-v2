from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.orm.exc import NoResultFound

from Delivery_app_BK.services.domain.client_form.terms_acceptance import (
    resolve_asserted_terms_version,
)
from Delivery_app_BK.errors import NotFound, ValidationFailed
from Delivery_app_BK.models import (
    ClientFormTermsVersion,
    Costumer,
    DeliveryPlan,
    Order,
    OrderDeliveryWindow,
    db,
)
from Delivery_app_BK.services.commands.order.apply_costumer_from_order import (
    apply_order_client_fields_to_costumer,
)
from Delivery_app_BK.services.commands.order.create_serializers import (
    serialize_created_order,
)
from Delivery_app_BK.services.commands.order.update_extensions import (
    OrderUpdateChangeFlags,
    OrderUpdateDelta,
    apply_order_update_extensions,
    build_order_update_extension_context,
)
from Delivery_app_BK.services.infra.events.builders.order import (
    build_client_form_submitted_event,
    build_delivery_window_rescheduled_by_user_event,
    build_order_edited_event,
    mark_client_form_submission,
)
from Delivery_app_BK.services.infra.events.emiters.order import emit_order_events
from Delivery_app_BK.services.domain.order.order_events import (
    CLIENT_FORM_SUBMISSION_SOURCES,
    ORDER_EDIT_SECTION_CLIENT_FORM,
    ORDER_EDIT_SECTION_CUSTOMER,
)
from Delivery_app_BK.services.infra.audit import (
    new_audit_event_id,
    record_order_audit_changes,
)
from Delivery_app_BK.services.domain.order.audit import (
    diff_order_audit_values,
    snapshot_order_audit_values,
)
from Delivery_app_BK.services.domain.order.plan_objective_labels import (
    normalize_order_plan_objective,
)
from Delivery_app_BK.services.domain.plan.route_freshness import touch_route_freshness
from Delivery_app_BK.services.utils import model_requires_team, require_team_id
from Delivery_app_BK.services.domain.order.delivery_windows import (
    resolve_order_delivery_windows_timezone,
    validate_and_normalize_delivery_windows,
    validate_same_local_day_delivery_windows,
)

from ...context import ServiceContext
from ..utils import extract_targets
from ..utils.inject_fields import inject_fields


FORBIDDEN_FIELD_KEYS = {
    "order_state_id",
    "delivery_plan_id",
}

FORBIDDEN_RELATIONSHIP_KEYS = {
    "state",
    "order_state",
    "state_history",
    "delivery_plan",
}

MUTABLE_FIELDS = {
    "order_plan_objective",
    "operation_type",
    "reference_number",
    "external_order_id",
    "external_source",
    "external_tracking_number",
    "external_tracking_link",
    "client_first_name",
    "client_last_name",
    "client_email",
    "client_primary_phone",
    "client_secondary_phone",
    "client_address",
    "help_to_carry",
    "marketing_messages",
    "delivery_windows",
    "order_notes",
    "accepted_terms_version_id",
    # Never accepted from a client — `_apply_terms_acceptance` stamps it beside a
    # validated version id, and is the only writer. Listed so that write passes.
    "terms_accepted_at",
}

ADDRESS_FIELDS = {"client_address"}
CUSTOMER_FIELDS = {
    "client_first_name",
    "client_last_name",
    "client_email",
    "client_primary_phone",
    "client_secondary_phone",
    "client_address",
}
WINDOW_FIELDS = {
    "delivery_windows",
}
DETAIL_FIELDS = MUTABLE_FIELDS.difference(WINDOW_FIELDS)


def update_order(ctx: ServiceContext):
    # `accepted_terms_version_id` is an FK without a mapped relationship on
    # Order, so field injection cannot resolve its target model on its own.
    # Reached when the in-store device patches an existing order: by this point
    # `_apply_terms_acceptance` has already replaced the asserted id with the
    # team's validated version id.
    ctx.set_relationship_map({"accepted_terms_version_id": ClientFormTermsVersion})
    targets = extract_targets(ctx)
    _extract_costumer_update_flags(targets)
    _extract_submission_sources(targets)
    _validate_targets_update_fields(targets)
    _apply_terms_acceptance(ctx, targets)

    updated_orders: list[Order] = []
    pending_events: list[dict[str, Any]] = []
    order_deltas: list[OrderUpdateDelta] = []
    extension_result = None
    delivery_plans_to_touch: list[DeliveryPlan] = []

    def _apply() -> None:
        nonlocal updated_orders, pending_events, order_deltas, extension_result, delivery_plans_to_touch
        updated_orders, pending_events, order_deltas = apply_order_updates(ctx, targets)
        extension_context = build_order_update_extension_context(ctx, order_deltas)
        extension_result = apply_order_update_extensions(ctx, order_deltas, extension_context)

        db.session.flush()
        for action in extension_result.post_flush_actions:
            action()

        if extension_result.instances:
            db.session.add_all(extension_result.instances)

        # Route freshness is a local-delivery concept, so it keys off the plan's
        # own type rather than the order's objective — the plan is what owns the
        # routes that go stale.
        delivery_plans_to_touch = [
            delta.delivery_plan
            for delta in order_deltas
            if (
                delta.delivery_plan is not None
                and getattr(delta.delivery_plan, "plan_type", None) == "local_delivery"
                and bool(delta.changed_sections)
            )
        ]
        for delivery_plan in delivery_plans_to_touch:
            touch_route_freshness(delivery_plan)
        if delivery_plans_to_touch:
            db.session.flush()

    try:
        with db.session.begin():
            _apply()
    except InvalidRequestError as exc:
        if "already begun" not in str(exc).lower():
            raise
        _apply()
        db.session.commit()

    if pending_events:
        emit_order_events(ctx, pending_events)

    bundles: list[dict[str, Any]] = []
    bundle_by_order_id = (extension_result.bundle_by_order_id if extension_result else {}) or {}
    

    for order_instance in updated_orders:
        order_id = getattr(order_instance, "id", None)
        extension_bundle = {}
        if order_id is not None:
            extension_bundle = (
                bundle_by_order_id.get(order_id)
                or bundle_by_order_id.get(str(order_id))
                or {}
            )
        bundle = {"order": serialize_created_order(order_instance)}
        

        bundle.update(extension_bundle)
        bundles.append(bundle)

    return {"updated": bundles}


def apply_order_updates(
    ctx: ServiceContext,
    targets: list[dict[str, Any]],
) -> tuple[list[Order], list[dict[str, Any]], list[OrderUpdateDelta]]:
    updated_orders: list[Order] = []
    pending_events: list[dict[str, Any]] = []
    order_deltas: list[OrderUpdateDelta] = []
    load_costumer = any(target.get("update_costumer") for target in targets)
    existing_orders = _resolve_orders_by_targets(ctx, targets, load_costumer=load_costumer)
    requested_costumers = _resolve_requested_costumers(ctx, targets)
    team_timezone = resolve_order_delivery_windows_timezone(ctx)

    for order_target in targets:
        target_id = order_target["target_id"]
        raw_fields = order_target["fields"]
        existing: Order = existing_orders[target_id]
        _reject_objective_change_on_assigned_order(existing, raw_fields)
        _apply_costumer_relink(existing, order_target, requested_costumers)
        fields_to_apply = _build_mutable_fields(raw_fields, order=existing)
        normalized_delivery_windows = _normalize_delivery_windows_for_update(
            raw_fields=raw_fields,
            team_timezone=team_timezone,
        )

        audit_before = snapshot_order_audit_values(existing)
        old_values = _capture_sync_values(existing)
        old_driver_visible_values = _capture_driver_visible_values(existing)
        _old_windows = list(existing.delivery_windows or [])
        old_earliest: datetime | None = min((_w.start_at for _w in _old_windows), default=None)
        old_latest: datetime | None = max((_w.end_at for _w in _old_windows), default=None)

        if fields_to_apply:
            inject_fields(ctx, existing, fields_to_apply)
        if normalized_delivery_windows is not None:
            _replace_order_delivery_windows(
                order=existing,
                normalized_delivery_windows=normalized_delivery_windows,
                team_id=ctx.team_id,
            )

        if order_target.get("update_costumer"):
            apply_order_client_fields_to_costumer(existing, raw_fields)

        submission_source = order_target.get("submission_source")
        if submission_source is not None:
            existing.client_form_submitted_at = datetime.now(timezone.utc)

        new_values = _capture_sync_values(existing)
        new_driver_visible_values = _capture_driver_visible_values(existing)
        _new_windows = list(existing.delivery_windows or [])
        new_earliest: datetime | None = min((_w.start_at for _w in _new_windows), default=None)
        new_latest: datetime | None = max((_w.end_at for _w in _new_windows), default=None)
        changed_sections = _resolve_changed_sections(
            old_values=old_driver_visible_values,
            new_values=new_driver_visible_values,
        )
        customer_fields_changed = _customer_fields_changed(
            old_values=old_driver_visible_values,
            new_values=new_driver_visible_values,
        )
        audit_changes = diff_order_audit_values(
            audit_before,
            snapshot_order_audit_values(existing),
        )
        pending_events.extend(
            _build_order_update_events(
                ctx,
                order=existing,
                changed_sections=changed_sections,
                customer_fields_changed=customer_fields_changed,
                audit_changes=audit_changes,
                submission_source=submission_source,
                window_bounds=(old_earliest, old_latest, new_earliest, new_latest),
            )
        )

        flags = _build_change_flags(old_values, new_values, fields_to_apply)
        order_deltas.append(
            OrderUpdateDelta(
                order_instance=existing,
                old_values=old_values,
                new_values=new_values,
                flags=flags,
                changed_sections=changed_sections,
                delivery_plan=_resolve_delivery_plan_for_order(existing),
            )
        )
        updated_orders.append(existing)

    return updated_orders, pending_events, order_deltas


def _build_order_update_events(
    ctx: ServiceContext,
    *,
    order: Order,
    changed_sections: tuple[str, ...],
    customer_fields_changed: bool,
    audit_changes: list,
    submission_source: str | None,
    window_bounds: tuple[datetime | None, datetime | None, datetime | None, datetime | None],
) -> list[dict[str, Any]]:
    """Build the edit event for one updated order and stage its audit rows.

    A customer's form relayed from a linked device is recorded like the public
    form: an edit in the client-form section plus CLIENT_FORM_SUBMITTED, both
    attributed to the customer. A staff edit that touches the customer's
    identity carries the CUSTOMER section instead, which is what pushes the
    change to Shopify.
    """
    submitted_event = None
    if submission_source is not None:
        # The customer's changes belong to their submission; the companion edit
        # event only carries the realtime "order updated" frame.
        submitted_event = build_client_form_submitted_event(order)
        submitted_event["event_id"] = new_audit_event_id()
        edit_event = build_order_edited_event(
            order_instance=order,
            changed_sections=[ORDER_EDIT_SECTION_CLIENT_FORM],
            audit_event_id=submitted_event["event_id"],
        )
    elif changed_sections:
        sections = list(changed_sections)
        if customer_fields_changed:
            sections.append(ORDER_EDIT_SECTION_CUSTOMER)
        if "schedule" in changed_sections:
            old_earliest, old_latest, new_earliest, new_latest = window_bounds
            edit_event = build_delivery_window_rescheduled_by_user_event(
                order_instance=order,
                old_earliest=old_earliest,
                old_latest=old_latest,
                new_earliest=new_earliest,
                new_latest=new_latest,
                changed_sections=sections,
            )
        else:
            edit_event = build_order_edited_event(
                order_instance=order,
                changed_sections=sections,
            )
    elif audit_changes:
        # Fields outside the driver-visible snapshot (notes, flags, external
        # tracking) still change the order; without an event their audit rows
        # would have no history entry to belong to.
        edit_event = build_order_edited_event(
            order_instance=order,
            changed_sections=["details"],
        )
    else:
        return []

    if submitted_event is None:
        edit_event["event_id"] = new_audit_event_id()
        record_order_audit_changes(
            ctx,
            order_id=order.id,
            team_id=order.team_id,
            event_id=edit_event["event_id"],
            changes=audit_changes,
        )
        return [edit_event]

    record_order_audit_changes(
        ctx,
        order_id=order.id,
        team_id=order.team_id,
        event_id=submitted_event["event_id"],
        changes=audit_changes,
        attribute_to_user=False,
    )
    events = [edit_event, submitted_event]
    for event in events:
        mark_client_form_submission(
            event,
            submission_source=submission_source,
            relayed_by_user_id=ctx.user_id,
        )
    return events


def _build_change_flags(
    old_values: dict[str, Any],
    new_values: dict[str, Any],
    applied_fields: dict[str, Any],
) -> OrderUpdateChangeFlags:
    touched_address = ADDRESS_FIELDS.intersection(applied_fields.keys())
    touched_window = WINDOW_FIELDS.intersection(applied_fields.keys())

    # Intent-driven flags: if these fields are submitted, run their extension flows.
    # This keeps route sync / warning recompute deterministic with PATCH payload intent.
    address_changed = bool(touched_address)
    window_changed = bool(touched_window)

    return OrderUpdateChangeFlags(
        address_changed=address_changed,
        window_changed=window_changed,
    )


def _capture_sync_values(order: Order) -> dict[str, Any]:
    return {
        "client_address": order.client_address,
    }


def _capture_driver_visible_values(order: Order) -> dict[str, Any]:
    return {
        "order_plan_objective": order.order_plan_objective,
        "operation_type": order.operation_type,
        "reference_number": order.reference_number,
        "external_order_id": order.external_order_id,
        "external_source": order.external_source,
        "tracking_number": order.tracking_number,
        "client_first_name": order.client_first_name,
        "client_last_name": order.client_last_name,
        "client_email": order.client_email,
        "client_primary_phone": order.client_primary_phone,
        "client_secondary_phone": order.client_secondary_phone,
        "client_address": order.client_address,
        "delivery_windows": [
            {
                "start_at": window.start_at.isoformat() if window.start_at else None,
                "end_at": window.end_at.isoformat() if window.end_at else None,
                "window_type": window.window_type,
            }
            for window in sorted(
                list(getattr(order, "delivery_windows", None) or []),
                key=lambda window: (
                    window.start_at.isoformat() if window.start_at else "",
                    window.end_at.isoformat() if window.end_at else "",
                    window.window_type or "",
                ),
            )
        ],
    }


def _resolve_changed_sections(
    *,
    old_values: dict[str, Any],
    new_values: dict[str, Any],
) -> tuple[str, ...]:
    changed_sections: list[str] = []

    if any(old_values.get(field) != new_values.get(field) for field in DETAIL_FIELDS):
        changed_sections.append("details")

    if any(old_values.get(field) != new_values.get(field) for field in WINDOW_FIELDS):
        changed_sections.append("schedule")

    return tuple(changed_sections)


def _customer_fields_changed(
    *,
    old_values: dict[str, Any],
    new_values: dict[str, Any],
) -> bool:
    return any(
        old_values.get(field) != new_values.get(field)
        for field in CUSTOMER_FIELDS
    )


def _resolve_delivery_plan_for_order(order: Order) -> DeliveryPlan | None:
    existing_delivery_plan = getattr(order, "delivery_plan", None)
    if existing_delivery_plan is not None:
        return existing_delivery_plan

    delivery_plan_id = getattr(order, "delivery_plan_id", None)
    if not delivery_plan_id:
        return None

    return db.session.get(DeliveryPlan, delivery_plan_id)


def _extract_costumer_update_flags(targets: list[dict[str, Any]]) -> None:
    """Pop the ``update_costumer`` flag and ``costumer`` relink request out of
    each target's fields.

    Both ride inside ``fields`` (the only key ``extract_targets`` keeps) but
    are not Order columns, so they are lifted onto the target and removed
    before field validation and injection ever see them.
    """
    for target in targets:
        fields = target.get("fields") or {}
        target["update_costumer"] = bool(fields.pop("update_costumer", False))
        target["requested_costumer_id"] = _extract_requested_costumer_id(
            target["target_id"], fields
        )


def _extract_submission_sources(targets: list[dict[str, Any]]) -> None:
    """Pop ``submission_source`` out of each target's fields.

    Present when the staff app relays a form the customer filled on a linked
    device; the update is then recorded as the customer's own submission.
    """
    for target in targets:
        fields = target.get("fields") or {}
        source = fields.pop("submission_source", None)
        if source is not None and source not in CLIENT_FORM_SUBMISSION_SOURCES:
            raise ValidationFailed(
                f"Target '{target['target_id']}' has an unsupported submission_source: {source!r}"
            )
        target["submission_source"] = source


def _extract_requested_costumer_id(target_id: Any, fields: dict[str, Any]) -> int | None:
    """Pop and validate the ``costumer`` relink request, if any.

    ``costumer: {costumer_id}`` mirrors the shape ``create_order`` accepts, so
    a client that already builds that object for creation can reuse it here to
    point an existing order at a different, already-existing Costumer.
    """
    costumer_ref = fields.pop("costumer", None)
    if costumer_ref is None:
        return None

    if not isinstance(costumer_ref, dict) or not isinstance(
        costumer_ref.get("costumer_id"), int
    ):
        raise ValidationFailed(
            f"Target '{target_id}' costumer must be an object with an integer costumer_id"
        )
    return costumer_ref["costumer_id"]


def _validate_targets_update_fields(targets: list[dict[str, Any]]) -> None:
    for target in targets:
        target_id = target["target_id"]
        fields = target.get("fields") or {}
        field_keys = set(fields.keys())

        forbidden_keys = sorted(
            field_keys & (FORBIDDEN_FIELD_KEYS | FORBIDDEN_RELATIONSHIP_KEYS)
        )
        if forbidden_keys:
            raise ValidationFailed(
                f"Target '{target_id}' contains forbidden fields for this endpoint: {forbidden_keys}"
            )

        unsupported_keys = sorted(field_keys - MUTABLE_FIELDS)
        if unsupported_keys:
            raise ValidationFailed(
                f"Target '{target_id}' contains unsupported fields for this endpoint: {unsupported_keys}"
            )


def _apply_terms_acceptance(ctx: ServiceContext, targets: list[dict[str, Any]]) -> None:
    """Validate any asserted terms acceptance and stamp the time it is recorded.

    Reached when the in-store device fills the form for an order that already
    exists, so the acceptance patches the order rather than being created with
    it. The submitted version is checked against the team's active one — a staff
    client cannot attach an arbitrary version and call it consent — and the
    timestamp is written here rather than taken from the request.
    """
    for target in targets:
        fields = target.get("fields") or {}
        if "accepted_terms_version_id" not in fields:
            continue

        # A client must never set the timestamp itself.
        fields.pop("terms_accepted_at", None)

        accepted_terms = resolve_asserted_terms_version(
            ctx.team_id,
            fields.get("accepted_terms_version_id"),
        )
        if accepted_terms is None:
            fields.pop("accepted_terms_version_id", None)
            continue

        fields["accepted_terms_version_id"] = accepted_terms.id
        fields["terms_accepted_at"] = datetime.now(timezone.utc)


def _reject_objective_change_on_assigned_order(
    order: Order,
    raw_fields: dict[str, Any],
) -> None:
    """An assigned order's objective belongs to its plan, not to the order.

    Writing it directly would desync the two and strand whatever the current
    domain built for the order — route stops, in the local delivery case. Moving
    the order onto a plan of the target type is the operation that legitimately
    changes it, and that path tears the old artifacts down. Repeating the current
    value is allowed so clients can echo a full order back unchanged.
    """
    if "order_plan_objective" not in raw_fields:
        return
    if getattr(order, "route_plan_id", None) is None:
        return

    requested = normalize_order_plan_objective(raw_fields.get("order_plan_objective"))
    # A null is the client saying it has nothing to assert about a field the plan
    # owns — the admin order form sends exactly that for any assigned order. It is
    # not a request to clear the objective, and `_build_mutable_fields` drops it.
    if requested is None:
        return

    current = normalize_order_plan_objective(
        getattr(order, "order_plan_objective", None)
    )
    if requested == current:
        return

    raise ValidationFailed(
        "order_plan_objective cannot be changed while the order is assigned to a "
        "route plan. Move the order to a plan of the target type instead."
    )


def _build_mutable_fields(
    raw_fields: dict[str, Any],
    order: Order | None = None,
) -> dict[str, Any]:
    fields = {
        key: value
        for key, value in raw_fields.items()
        if key in MUTABLE_FIELDS and key != "delivery_windows"
    }

    # An assigned order takes its objective from its plan, so a write here is
    # never meaningful. Dropping it stops a client that echoes the field back
    # from clearing a value the plan is the source of truth for.
    if order is not None and getattr(order, "route_plan_id", None) is not None:
        fields.pop("order_plan_objective", None)

    return fields


def _normalize_delivery_windows_for_update(
    *,
    raw_fields: dict[str, Any],
    team_timezone,
):
    if "delivery_windows" not in raw_fields:
        return None

    normalized = validate_and_normalize_delivery_windows(
        raw_fields.get("delivery_windows"),
    )
    validate_same_local_day_delivery_windows(
        normalized,
        team_timezone=team_timezone,
    )
    return normalized


def _replace_order_delivery_windows(
    *,
    order: Order,
    normalized_delivery_windows,
    team_id: int | None,
) -> None:
    order.delivery_windows.clear()
    for row in normalized_delivery_windows:
        order.delivery_windows.append(
            OrderDeliveryWindow(
                team_id=team_id,
                client_id=row.client_id,
                start_at=row.start_at,
                end_at=row.end_at,
                window_type=row.window_type,
            ),
        )


def _resolve_requested_costumers(
    ctx: ServiceContext,
    targets: list[dict[str, Any]],
) -> dict[int, Costumer]:
    """Batch-load every ``Costumer`` a target asked to relink onto, team-scoped.

    Addresses/phones are preloaded so a relink combined with
    ``update_costumer: true`` can push the submitted client_* fields onto the
    newly linked costumer without a second round trip.
    """
    requested_ids = {
        target["requested_costumer_id"]
        for target in targets
        if target.get("requested_costumer_id") is not None
    }
    if not requested_ids:
        return {}

    team_id = None
    if model_requires_team(Costumer) and ctx.check_team_id:
        team_id = require_team_id(ctx)

    query = (
        db.session.query(Costumer)
        .options(selectinload(Costumer.addresses), selectinload(Costumer.phones))
        .filter(Costumer.id.in_(requested_ids))
    )
    if team_id is not None:
        query = query.filter(Costumer.team_id == team_id)

    by_id = {costumer.id: costumer for costumer in query.all()}
    missing = sorted(requested_ids - by_id.keys())
    if missing:
        raise NotFound(f"Costumers not found: {missing}")
    return by_id


def _apply_costumer_relink(
    order: Order,
    order_target: dict[str, Any],
    requested_costumers: dict[int, Costumer],
) -> None:
    """Point ``order`` at a different, already-existing Costumer, if requested.

    Runs independent of the ``update_costumer`` flag: relinking is the client
    asserting which costumer instance the order belongs to, while
    ``update_costumer`` separately controls whether the submitted client_*
    fields get pushed onto whichever costumer ends up linked.
    """
    requested_costumer_id = order_target.get("requested_costumer_id")
    if requested_costumer_id is None or requested_costumer_id == order.costumer_id:
        return
    order.costumer = requested_costumers[requested_costumer_id]


def _resolve_orders_by_targets(
    ctx: ServiceContext,
    targets: list[dict[str, Any]],
    *,
    load_costumer: bool = False,
) -> dict[int | str, Order]:
    target_ids = [target["target_id"] for target in targets]
    int_ids = [value for value in target_ids if isinstance(value, int)]
    client_ids = [value for value in target_ids if isinstance(value, str)]

    orders_by_id: dict[int, Order] = {}
    orders_by_client_id: dict[str, Order] = {}
    team_id = None

    if model_requires_team(Order) and ctx.check_team_id:
        team_id = require_team_id(ctx)

    load_options = [joinedload(Order.delivery_plan), selectinload(Order.delivery_windows)]
    if load_costumer:
        load_options.extend(
            [
                selectinload(Order.costumer).selectinload(Costumer.addresses),
                selectinload(Order.costumer).selectinload(Costumer.phones),
            ]
        )

    if int_ids:
        query = (
            db.session.query(Order)
            .options(*load_options)
            .filter(Order.id.in_(int_ids))
        )
        if team_id is not None:
            query = query.filter(Order.team_id == team_id)
        for order in query.all():
            orders_by_id[order.id] = order

    if client_ids:
        query = (
            db.session.query(Order)
            .options(*load_options)
            .filter(Order.client_id.in_(client_ids))
        )
        if team_id is not None:
            query = query.filter(Order.team_id == team_id)
        for order in query.all():
            orders_by_client_id[order.client_id] = order

    resolved: dict[int | str, Order] = {}
    missing: list[int | str] = []
    for target_id in target_ids:
        order = (
            orders_by_id.get(target_id)
            if isinstance(target_id, int)
            else orders_by_client_id.get(target_id)
        )
        if order is None:
            missing.append(target_id)
            continue
        resolved[target_id] = order

    if missing:
        raise NoResultFound(f"Orders not found: {missing}")

    return resolved
