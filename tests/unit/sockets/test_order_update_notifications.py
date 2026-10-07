from types import SimpleNamespace

from Delivery_app_BK.services.domain.order.order_events import OrderEvent
from Delivery_app_BK.sockets import notifications as module


def _row(field_name, from_value, to_value):
    return SimpleNamespace(
        field_name=field_name,
        from_value=from_value,
        to_value=to_value,
        entity_type="order",
        entity_id=None,
        entity_label=None,
    )


def test_staff_update_description_lists_what_changed():
    description = module._build_order_updated_description(
        order_label="Order #2549",
        payload={
            "notification_origin": "user",
            "notification_change_labels": ["Email", "Address", "Phone", "Customer note"],
            "changed_sections": ["details"],
        },
    )

    assert description == "Order #2549 updated: Email, Address and 2 more."


def test_update_without_recorded_changes_falls_back_to_sections():
    description = module._build_order_updated_description(
        order_label="Order #2549",
        payload={
            "notification_origin": "user",
            "notification_change_labels": [],
            "changed_sections": ["details", "items"],
        },
    )

    assert description == "Order #2549 details and items were updated."


def test_client_submission_description_names_the_client():
    with_changes = module._build_order_updated_description(
        order_label="Order #2549",
        payload={
            "notification_origin": "client",
            "notification_change_labels": ["Email"],
        },
    )
    without_changes = module._build_order_updated_description(
        order_label="Order #2549",
        payload={"changed_sections": ["client_form_submission"]},
    )

    assert with_changes == "Client submitted the form for Order #2549 and updated Email."
    # The realtime preview has no resolved origin; it is derived from the payload.
    assert without_changes == "Client submitted the form for Order #2549."


def test_change_labels_are_read_from_the_submission_event_and_skip_first_fills(monkeypatch):
    calls = []

    def fake_list(**kwargs):
        calls.append(kwargs)
        return [_row("client_email", None, "a@x.com"), _row("client_last_name", "Doe", "Roe")]

    monkeypatch.setattr(module, "list_order_event_audit_changes", fake_list)

    labels = module._resolve_order_change_labels(
        event_name="order.updated",
        event_id="edit-event",
        team_id=7,
        order_id=14,
        payload={"audit_event_id": "submission-event"},
        origin="client",
    )

    assert calls == [{"team_id": 7, "order_id": 14, "event_id": "submission-event"}]
    assert labels == ["Last name"]


def test_change_labels_use_the_event_itself_for_staff_edits(monkeypatch):
    calls = []

    def fake_list(**kwargs):
        calls.append(kwargs)
        return [_row("client_email", None, "a@x.com")]

    monkeypatch.setattr(module, "list_order_event_audit_changes", fake_list)

    labels = module._resolve_order_change_labels(
        event_name="order.updated",
        event_id="edit-event",
        team_id=7,
        order_id=14,
        payload={},
        origin="user",
    )

    assert calls[0]["event_id"] == "edit-event"
    assert labels == ["Email"]


def test_change_labels_are_only_loaded_for_updates(monkeypatch):
    monkeypatch.setattr(
        module,
        "list_order_event_audit_changes",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("should not query")),
    )

    assert module._resolve_order_change_labels(
        event_name="order.state_changed",
        event_id="e",
        team_id=7,
        order_id=14,
        payload={},
        origin="user",
    ) == []


def test_notification_item_carries_actor_subject_and_truncated_changes():
    actor = SimpleNamespace(id=5, username="david", email=None)

    item = module.build_notification_item(
        event_id="e",
        recipient_user_id=9,
        app_scope="admin",
        kind="order.updated",
        entity_type="order",
        entity_id=14,
        team_id=7,
        actor=actor,
        actor_role="Dispatcher",
        title="Order updated",
        description="Order #2549 updated: Email, Address and 3 more.",
        occurred_at="2026-10-07T10:00:00+00:00",
        target={"kind": "order_detail"},
        subject_label="Order #2549",
        change_labels=["Email", "Address", "Phone", "Note", "Window"],
    )

    assert item["actor_kind"] == "user"
    assert item["actor_role"] == "Dispatcher"
    assert item["subject_label"] == "Order #2549"
    assert item["change_labels"] == ["Email", "Address", "Phone"]
    assert item["change_count"] == 5


def test_notification_item_without_actor_is_the_systems():
    item = module.build_notification_item(
        event_id="e",
        recipient_user_id=9,
        app_scope="admin",
        kind="route_plan.updated",
        entity_type="delivery_plan",
        entity_id=3,
        team_id=7,
        actor=None,
        title="Route plan updated",
        description="Route plan was updated.",
        occurred_at="2026-10-07T10:00:00+00:00",
        target={"kind": "local_delivery_workspace"},
    )

    assert item["actor_kind"] == "system"
    assert item["actor_role"] is None
    assert "subject_label" not in item
    assert "change_labels" not in item


def test_client_update_title():
    assert module._build_order_notification_title("order.updated", "client") == "Client form submitted"
    assert module._build_order_notification_title("order.updated", "user") == "Order updated"


def _order_target(event_name, order_event_id):
    return module._build_notification_target(
        app_scope="admin",
        event_name=event_name,
        order=SimpleNamespace(id=14),
        payload={},
        route_id=None,
        entity_type="order",
        entity_id=14,
        order_event_id=order_event_id,
    )


def test_update_notifications_focus_the_event_and_client_ones_their_submission():
    staff = module._resolve_order_focus_event_id(
        event_name="order.updated", event_id="edit-event", payload={}
    )
    client = module._resolve_order_focus_event_id(
        event_name="order.updated",
        event_id="edit-event",
        payload={"audit_event_id": "submission-event"},
    )
    status = module._resolve_order_focus_event_id(
        event_name="order.state_changed", event_id="status-event", payload={}
    )

    assert (staff, client, status) == ("edit-event", "submission-event", "status-event")
    assert _order_target("order.updated", client)["params"] == {
        "orderId": 14,
        "orderEventId": "submission-event",
    }


def test_created_notifications_open_the_order_without_focusing_an_event():
    focus = module._resolve_order_focus_event_id(
        event_name="order.created", event_id="created-event", payload={}
    )

    assert focus is None
    assert _order_target("order.created", focus)["params"] == {"orderId": 14}


def test_plan_update_description_lists_what_changed():
    description = module._describe_route_plan_updated(
        None,
        {
            "label": "Plan for October 15",
            "plan_type": "local_delivery",
            "notification_plan_changes": ["dates", "route settings"],
        },
    )

    assert description == 'Local delivery plan "Plan for October 15": dates and route settings updated.'


def test_plan_update_description_without_changes_stays_generic():
    assert (
        module._describe_route_plan_updated(None, {"plan_type": "local_delivery"})
        == "Local delivery plan was updated."
    )


def test_route_settings_save_is_not_called_an_optimization():
    description = module._describe_route_solution_updated(
        None,
        {"label": "variant 1", "notification_change_hint": "settings_updated"},
    )

    assert description == 'Route "variant 1" - settings were updated.'


def test_route_created_with_its_plan_reaches_drivers_but_not_admins(monkeypatch):
    stored = []
    monkeypatch.setattr(
        module,
        "resolve_admin_notification_recipients",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("admins already get the plan")),
    )
    monkeypatch.setattr(
        module,
        "resolve_driver_notification_recipients",
        lambda **_kwargs: [{"user_id": 8, "app_scope": "driver", "route_id": 3}],
    )
    monkeypatch.setattr(module, "_resolve_actor_role_label", lambda *_args: None)
    monkeypatch.setattr(module, "_build_notification_target", lambda **_kwargs: {"kind": "route_execution"})
    monkeypatch.setattr(module, "_build_related_ids", lambda **_kwargs: {})
    monkeypatch.setattr(module, "current_app", SimpleNamespace(logger=SimpleNamespace(info=lambda *_a: None)))
    monkeypatch.setattr(
        module,
        "_store_and_emit_notification",
        lambda user_id, app_scope, notification: stored.append((user_id, app_scope)),
    )

    module.notify_delivery_planning_event(
        event_id="e",
        event_name="route_solution.created",
        team_id=7,
        entity_type="route_solution",
        entity_id=3,
        payload={"route_solution_id": 3, "label": "variant 1"},
        occurred_at="2026-10-07T10:00:00+00:00",
        actor=None,
        notify_admins=False,
    )

    assert stored == [(8, "driver")]


def test_events_folded_into_a_plan_change_do_not_notify():
    assert module._should_suppress_order_notification(
        {"original_event_name": "order_status_changed", "notification_folded_into": "lead"}
    )


def _stub_plans(monkeypatch, plans):
    monkeypatch.setattr(
        module,
        "db",
        SimpleNamespace(session=SimpleNamespace(get=lambda _model, plan_id: plans.get(plan_id))),
    )


PLAN_CHANGED = OrderEvent.DELIVERY_PLAN_CHANGED.value
RESCHEDULED = OrderEvent.DELIVERY_RESCHEDULED.value
OCT_17 = ("2026-10-17T00:00:00+00:00", "2026-10-17T23:59:59.999999+00:00")
OCT_19 = ("2026-10-19T00:00:00+00:00", "2026-10-19T23:59:59.999999+00:00")
PLANS = {
    5: SimpleNamespace(label="Plan for October 17", plan_type="local_delivery"),
    6: SimpleNamespace(label="Plan for October 19", plan_type="local_delivery"),
}


def _plan_change(old_plan_id, new_plan_id, old_dates=(None, None), new_dates=(None, None), **extra):
    return {
        "original_event_name": PLAN_CHANGED,
        "old_route_plan_id": old_plan_id,
        "new_route_plan_id": new_plan_id,
        "notification_old_plan_start": old_dates[0],
        "notification_old_plan_end": old_dates[1],
        "notification_new_plan_start": new_dates[0],
        "notification_new_plan_end": new_dates[1],
        **extra,
    }


def _with_move(payload, order=None):
    return {**payload, **module._resolve_plan_move(payload, order)}


def test_scheduling_reads_as_one_notification_with_date_plan_and_status(monkeypatch):
    _stub_plans(monkeypatch, PLANS)
    payload = _with_move(
        _plan_change(
            None, 6, new_dates=OCT_19,
            notification_old_order_state_id=1, notification_new_order_state_id=2,
        )
    )

    assert payload["notification_plan_move_action"] == "scheduled"
    assert module._build_order_notification_title("order.updated", "user", "scheduled") == "Order scheduled"
    assert module._build_plan_move_detail(payload) == (
        'Oct 19 · Local delivery plan "Plan for October 19" · Draft → Confirmed'
    )
    assert module._build_order_updated_description(order_label="Order #4505", payload=payload) == (
        'Order #4505 scheduled for Oct 19 on Local delivery plan "Plan for October 19" (Draft → Confirmed).'
    )


def test_moving_to_a_plan_on_another_day_is_a_reschedule(monkeypatch):
    _stub_plans(monkeypatch, PLANS)
    payload = _with_move(_plan_change(5, 6, old_dates=OCT_17, new_dates=OCT_19))

    assert payload["notification_plan_move_action"] == "rescheduled"
    assert module._build_order_notification_title("order.updated", "user", "rescheduled") == "Order rescheduled"
    assert module._build_plan_move_detail(payload) == (
        "Oct 17 → Oct 19 · Plan for October 17 → Plan for October 19"
    )
    assert module._build_order_updated_description(order_label="Order #4505", payload=payload) == (
        "Order #4505 rescheduled from Oct 17 to Oct 19 (Plan for October 17 → Plan for October 19)."
    )


def test_moving_to_a_plan_on_the_same_day_is_a_move(monkeypatch):
    _stub_plans(monkeypatch, PLANS)
    payload = _with_move(_plan_change(5, 6, old_dates=OCT_17, new_dates=OCT_17))

    assert payload["notification_plan_move_action"] == "moved"
    assert module._build_plan_move_detail(payload) == "Plan for October 17 → Plan for October 19"
    assert module._build_order_updated_description(order_label="Order #4505", payload=payload) == (
        "Order #4505 moved from Plan for October 17 to Plan for October 19."
    )


def test_unscheduling_names_the_plan_the_order_left(monkeypatch):
    _stub_plans(monkeypatch, PLANS)
    payload = _with_move(_plan_change(5, None))

    assert payload["notification_plan_move_action"] == "unscheduled"
    assert module._build_plan_move_detail(payload) == 'From Local delivery plan "Plan for October 17"'
    assert module._build_order_updated_description(order_label="Order #4505", payload=payload) == (
        'Order #4505 removed from Local delivery plan "Plan for October 17".'
    )


def test_a_reschedule_on_its_own_shows_the_date_change(monkeypatch):
    _stub_plans(monkeypatch, PLANS)
    payload = _with_move(
        {
            "original_event_name": RESCHEDULED,
            "old_plan_start": OCT_17[0],
            "old_plan_end": OCT_17[1],
            "new_plan_start": OCT_19[0],
            "new_plan_end": OCT_19[1],
            "reason": "plan_window_changed",
        },
        order=SimpleNamespace(route_plan_id=6),
    )

    assert payload["notification_plan_move_action"] == "rescheduled"
    assert module._build_plan_move_detail(payload) == (
        'Oct 17 → Oct 19 · Local delivery plan "Plan for October 19"'
    )


def test_plan_date_ranges_are_formatted_as_calendar_days():
    assert module._format_plan_dates(*OCT_19) == "Oct 19"
    assert module._format_plan_dates(OCT_17[0], OCT_19[1]) == "Oct 17 – Oct 19"
    assert module._format_plan_dates(None, None) is None


def test_other_order_updates_are_not_plan_moves():
    assert module._resolve_plan_move({"original_event_name": "order_edited"}) == {}


def test_local_delivery_order_targets_open_its_plan():
    order = SimpleNamespace(id=14, order_plan_objective="local_delivery", route_plan_id=6, route_group_id=9)
    target = module._build_notification_target(
        app_scope="admin",
        event_name="order.updated",
        order=order,
        payload={},
        route_id=None,
        entity_type="order",
        entity_id=14,
    )

    assert target["params"] == {"orderId": 14, "planId": 6, "routeGroupId": 9}


def test_other_orders_open_without_a_plan():
    pickup = SimpleNamespace(id=14, order_plan_objective="store_pickup", route_plan_id=6, route_group_id=None)
    unscheduled = SimpleNamespace(id=15, order_plan_objective="local_delivery", route_plan_id=None, route_group_id=None)

    assert module._order_plan_params(pickup) == {}
    assert module._order_plan_params(unscheduled) == {}


def _stub_orders_and_team(monkeypatch, orders, time_zone="Europe/Stockholm"):
    def _get(model, key):
        if model is module.Team:
            return SimpleNamespace(time_zone=time_zone)
        return orders.get(key)

    monkeypatch.setattr(module, "db", SimpleNamespace(session=SimpleNamespace(get=_get)))


def _route_payload(hint, **extra):
    return {
        "label": "variant 1",
        "plan_label": "Plan for October 19",
        "notification_change_hint": hint,
        **extra,
    }


ARRIVALS = {
    "notification_arrival_change_count": 5,
    "notification_arrival_changes": [
        {"order_id": 1, "old_arrival": "2026-10-19T06:30:00+00:00", "new_arrival": "2026-10-19T07:10:00+00:00"},
        {"order_id": 2, "old_arrival": "2026-10-19T07:00:00+00:00", "new_arrival": "2026-10-19T07:20:00+00:00"},
    ],
}


def test_arrival_summary_previews_moves_in_the_team_time_zone(monkeypatch):
    _stub_orders_and_team(
        monkeypatch,
        {
            1: SimpleNamespace(id=1, order_scalar_id=4505, external_source=None, reference_number=None),
            2: SimpleNamespace(id=2, order_scalar_id=4506, external_source=None, reference_number=None),
        },
    )

    summary = module._summarize_arrival_changes(ARRIVALS, team_id=7)

    assert summary == (
        "5 arrival times changed · Order #4505 08:30 → 09:10 · Order #4506 09:00 → 09:20 +3 more"
    )


def test_route_reorder_reads_as_a_headline_with_arrivals():
    payload = _route_payload("stops_reordered", notification_arrival_summary="5 arrival times changed")

    assert module._resolve_planning_headline("route_solution.updated", payload) == (
        'Route "variant 1"',
        "reordered stops on",
    )
    assert module._build_planning_detail("route_solution.updated", payload) == (
        "Plan for October 19 · 5 arrival times changed"
    )
    assert module._describe_route_solution_updated(None, payload).endswith(
        "stops were reordered. 5 arrival times changed."
    )


def test_selecting_a_variant_is_not_called_an_optimization():
    payload = _route_payload("variant_selected")

    assert module._resolve_planning_headline("route_solution.updated", payload)[1] == "switched to"
    assert "is now the selected variant" in module._describe_route_solution_updated(None, payload)


def test_routes_without_a_known_change_keep_the_plain_layout():
    payload = _route_payload("times_updated")

    assert module._resolve_planning_headline("route_solution.updated", payload) == (None, None)
    assert module._build_planning_detail("route_solution.updated", payload) is None


def test_quiet_reschedules_do_not_notify():
    assert module._should_suppress_order_notification(
        {"original_event_name": "order_rescheduled", "notification_suppressed": True}
    )


def test_a_plan_move_notification_says_where_not_which_fields(monkeypatch):
    order = SimpleNamespace(
        id=14, order_scalar_id=4498, external_source=None, reference_number=None,
        order_plan_objective="local_delivery", route_plan_id=6, route_group_id=9,
    )
    plans = {5: PLANS[5], 6: PLANS[6]}

    def _get(model, key):
        if model is module.Order:
            return order
        return plans.get(key)

    stored = []
    monkeypatch.setattr(module, "db", SimpleNamespace(session=SimpleNamespace(get=_get)))
    monkeypatch.setattr(
        module,
        "_resolve_order_change_labels",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("a plan move describes itself")),
    )
    monkeypatch.setattr(module, "resolve_admin_notification_recipients", lambda **_kwargs: [{"user_id": 9, "app_scope": "admin"}])
    monkeypatch.setattr(module, "resolve_driver_notification_recipients", lambda **_kwargs: [])
    monkeypatch.setattr(module, "_resolve_actor_role_label", lambda *_args: "Admin")
    monkeypatch.setattr(
        module,
        "_store_and_emit_notification",
        lambda _user_id, _scope, notification: stored.append(notification),
    )

    module.notify_order_event(
        event_id="plan-change",
        event_name="order.updated",
        team_id=7,
        order_id=14,
        payload={
            "original_event_name": PLAN_CHANGED,
            **_plan_change(5, 6, old_dates=OCT_17, new_dates=OCT_19),
        },
        occurred_at="2026-10-07T10:00:00+00:00",
        actor=SimpleNamespace(id=2, username="loorenz", email=None),
    )

    notification = stored[0]
    assert notification["action_label"] == "rescheduled"
    assert "change_labels" not in notification
    assert notification["detail"] == "Oct 17 → Oct 19 · Plan for October 17 → Plan for October 19"
