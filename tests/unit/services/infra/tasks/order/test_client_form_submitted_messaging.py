from importlib import import_module
from types import SimpleNamespace


email_module = import_module("Delivery_app_BK.services.infra.tasks.order.send_email")
sms_module = import_module("Delivery_app_BK.services.infra.tasks.order.send_sms")


def _build_action(module, *, action_id: int, order) -> SimpleNamespace:
    event = SimpleNamespace(
        id=action_id + 100,
        order=order,
        team_id=7,
        event_name="client_form_submitted",
        payload={},
    )
    return SimpleNamespace(
        id=action_id,
        event_id=event.id,
        event=event,
        team_id=7,
        status=module.OrderEventAction.STATUS_PENDING,
        scheduled_for=None,
        attempts=0,
        schedule_anchor_type=None,
        last_error=None,
        processed_at=None,
    )


def _build_order(**overrides) -> SimpleNamespace:
    fields = {
        "client_email": "client@example.com",
        "client_primary_phone": {"prefix": "+46", "number": "2020203"},
        "client_secondary_phone": None,
        "team": None,
        "route_plan": None,
        "order_plan_objective": None,
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _configure_email_task(monkeypatch, action, send_calls, *, template=None, resolve_calls=None):
    monkeypatch.setattr(email_module.db.session, "get", lambda _model, _id: action)
    monkeypatch.setattr(email_module.db.session, "commit", lambda: None)
    monkeypatch.setattr(email_module, "notify_order_action_changed", lambda _action: None)
    monkeypatch.setattr(email_module, "get_existing_client_form_url", lambda _order: None)

    def _resolve(**kwargs):
        if resolve_calls is not None:
            resolve_calls.append(kwargs)
        return template

    monkeypatch.setattr(email_module, "resolve_message_template", _resolve)
    monkeypatch.setattr(
        email_module,
        "send_email_message",
        lambda **kwargs: send_calls.append(kwargs),
    )


def _configure_sms_task(monkeypatch, action, send_calls, *, template=None, resolve_calls=None):
    monkeypatch.setattr(sms_module.db.session, "get", lambda _model, _id: action)
    monkeypatch.setattr(sms_module.db.session, "commit", lambda: None)
    monkeypatch.setattr(sms_module, "notify_order_action_changed", lambda _action: None)
    monkeypatch.setattr(sms_module, "get_existing_client_form_url", lambda _order: None)

    def _resolve(**kwargs):
        if resolve_calls is not None:
            resolve_calls.append(kwargs)
        return template

    monkeypatch.setattr(sms_module, "resolve_message_template", _resolve)
    monkeypatch.setattr(
        sms_module,
        "send_sms_message",
        lambda **kwargs: send_calls.append(kwargs),
    )


def test_missing_email_fails_only_email_channel(monkeypatch):
    order = _build_order(client_email="")
    template = SimpleNamespace(enable=True)
    email_action = _build_action(email_module, action_id=1, order=order)
    sms_action = _build_action(sms_module, action_id=2, order=order)
    email_calls = []
    sms_calls = []
    _configure_email_task(monkeypatch, email_action, email_calls, template=template)
    email_module.send_email(email_action.id)

    _configure_sms_task(monkeypatch, sms_action, sms_calls, template=template)
    sms_module.send_sms(sms_action.id)

    assert email_action.status == email_module.OrderEventAction.STATUS_FAILED
    assert email_action.last_error == "Order has no client email"
    assert email_calls == []
    assert sms_action.status == sms_module.OrderEventAction.STATUS_SUCCESS
    assert sms_calls[0]["recipient_phone"] == "+462020203"
    assert sms_calls[0]["event_name"] == "client_form_submitted"
    assert sms_calls[0]["template"] is template


def test_missing_phone_fails_only_sms_channel(monkeypatch):
    order = _build_order(client_primary_phone=None)
    template = SimpleNamespace(enable=True)
    email_action = _build_action(email_module, action_id=3, order=order)
    sms_action = _build_action(sms_module, action_id=4, order=order)
    email_calls = []
    sms_calls = []
    _configure_email_task(monkeypatch, email_action, email_calls, template=template)
    email_module.send_email(email_action.id)

    _configure_sms_task(monkeypatch, sms_action, sms_calls, template=template)
    sms_module.send_sms(sms_action.id)

    assert email_action.status == email_module.OrderEventAction.STATUS_SUCCESS
    assert email_calls[0]["recipient"] == "client@example.com"
    assert email_calls[0]["event_name"] == "client_form_submitted"
    assert email_calls[0]["template"] is template
    assert sms_action.status == sms_module.OrderEventAction.STATUS_FAILED
    assert sms_action.last_error == "Order has no valid recipient phone number"
    assert sms_calls == []


def test_tasks_resolve_the_template_for_the_orders_plan_type(monkeypatch):
    order = _build_order(route_plan=SimpleNamespace(plan_type="store_pickup"))
    template = SimpleNamespace(enable=True)
    email_action = _build_action(email_module, action_id=5, order=order)
    sms_action = _build_action(sms_module, action_id=6, order=order)
    email_resolves, sms_resolves = [], []

    _configure_email_task(monkeypatch, email_action, [], template=template, resolve_calls=email_resolves)
    email_module.send_email(email_action.id)
    _configure_sms_task(monkeypatch, sms_action, [], template=template, resolve_calls=sms_resolves)
    sms_module.send_sms(sms_action.id)

    assert email_resolves == [
        {"team_id": 7, "channel": "email", "event_name": "client_form_submitted", "plan_type": "store_pickup"}
    ]
    assert sms_resolves == [
        {"team_id": 7, "channel": "sms", "event_name": "client_form_submitted", "plan_type": "store_pickup"}
    ]


def test_missing_template_for_plan_type_skips_and_names_the_plan_type(monkeypatch):
    order = _build_order(route_plan=SimpleNamespace(plan_type="international_shipping"))
    email_action = _build_action(email_module, action_id=7, order=order)
    sms_action = _build_action(sms_module, action_id=8, order=order)
    email_calls, sms_calls = [], []

    _configure_email_task(monkeypatch, email_action, email_calls, template=None)
    email_module.send_email(email_action.id)
    _configure_sms_task(monkeypatch, sms_action, sms_calls, template=SimpleNamespace(enable=False))
    sms_module.send_sms(sms_action.id)

    assert email_action.status == email_module.OrderEventAction.STATUS_SKIPPED
    assert "international_shipping" in email_action.last_error
    assert sms_action.status == sms_module.OrderEventAction.STATUS_SKIPPED
    assert "international_shipping" in sms_action.last_error
    assert email_calls == [] and sms_calls == []
