import importlib
from contextlib import contextmanager
from types import SimpleNamespace

from Delivery_app_BK.services.requests.order.create_order import OrderCreateRequest


module = importlib.import_module("Delivery_app_BK.services.commands.order.create_order")


@contextmanager
def _tx():
    yield


class _DummySession:
    def begin(self):
        return _tx()

    def add_all(self, _instances):
        return None

    def flush(self):
        return None


def _build_ctx():
    return SimpleNamespace(
        set_relationship_map=lambda *_args, **_kwargs: None,
        team_id=1,
        identity={},
    )


def test_create_order_uses_route_plan_keyword_for_objective(monkeypatch):
    route_plan = SimpleNamespace(
        id=688,
        team_id=1,
        total_weight_g=0.0,
        total_volume_cm3=0.0,
        total_item_count=0,
        total_orders=1,
    )
    request = OrderCreateRequest(
        fields={
            "client_id": "order_1",
            "client_email": "user@example.com",
        },
        items=[],
        delivery_plan_id=route_plan.id,
        costumer=SimpleNamespace(costumer_id=4089, client_id=None, first_name=None, last_name=None, email=None, primary_phone=None, address=None),
        delivery_windows=[],
    )

    monkeypatch.setattr(module, "db", SimpleNamespace(session=_DummySession()))
    monkeypatch.setattr(module, "extract_fields", lambda _ctx: [{"idx": 0}])
    monkeypatch.setattr(module, "parse_create_order_request", lambda _raw: request)
    monkeypatch.setattr(module, "_load_route_plans_by_id", lambda _ctx, _ids: {route_plan.id: route_plan})
    monkeypatch.setattr(module, "resolve_or_create_costumers", lambda _ctx, _inputs: [SimpleNamespace(id=4089)])
    monkeypatch.setattr(module, "reserve_order_scalar_ids", lambda _ctx, _count: [1])
    monkeypatch.setattr(module, "resolve_order_delivery_windows_timezone", lambda _ctx: "Europe/Stockholm")
    monkeypatch.setattr(module, "validate_and_normalize_delivery_windows", lambda windows: windows)
    monkeypatch.setattr(module, "validate_same_local_day_delivery_windows", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "generate_tracking_identifiers", lambda _order: None)
    monkeypatch.setattr(module, "recompute_plan_totals", lambda _plan: None)
    monkeypatch.setattr(module, "touch_route_freshness", lambda _plan: None)
    monkeypatch.setattr(module, "build_order_created_event", lambda _order: {})
    monkeypatch.setattr(module, "emit_order_events", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "serialize_created_order", lambda order: {"id": order.id})
    monkeypatch.setattr(module, "serialize_created_items", lambda _items: [])

    def _create_instance(_ctx, model, fields):
        if model is module.Order:
            return SimpleNamespace(
                id=1,
                client_id=fields["client_id"],
                order_plan_objective=fields.get("order_plan_objective"),
                items=[],
                delivery_windows=[],
                route_plan_id=None,
                route_plan=None,
                costumer_id=None,
                tracking_token_hash=None,
                items_updated_at=None,
            )
        raise AssertionError(f"Unexpected model: {model}")

    captured = {}

    def _apply_order_plan_objective(**kwargs):
        captured.update(kwargs)
        return module.PlanObjectiveCreateResult()

    monkeypatch.setattr(module, "create_instance", _create_instance)
    monkeypatch.setattr(module, "apply_order_plan_objective", _apply_order_plan_objective)

    module.create_order(_build_ctx())

    assert captured["route_plan"] is route_plan
    assert "delivery_plan" not in captured
