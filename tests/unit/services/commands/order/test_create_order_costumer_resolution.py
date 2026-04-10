import importlib
from contextlib import contextmanager
from types import SimpleNamespace

module = importlib.import_module("Delivery_app_BK.services.commands.order.create_order")
from Delivery_app_BK.services.requests.order.create_order import (
    OrderCostumerRequest,
    OrderCreateRequest,
)


@contextmanager
def _tx():
    yield


class _DummySession:
    def __init__(self) -> None:
        self.added: list[object] = []

    def begin(self):
        return _tx()

    def add_all(self, instances):
        self.added.extend(instances)

    def flush(self):
        return None


def _build_request(
    *,
    client_id: str,
    costumer_id: int | None,
    costumer_client_id: str | None = None,
    email: str | None = None,
):
    return OrderCreateRequest(
        fields={
            "client_id": client_id,
            "client_first_name": "Name",
            "client_last_name": "Last",
            "client_email": email,
        },
        items=[],
        route_plan_id=None,
        costumer=OrderCostumerRequest(
            costumer_id=costumer_id,
            client_id=costumer_client_id,
            first_name=None,
            last_name=None,
            email=None,
            primary_phone=None,
            address=None,
        )
        if costumer_id is not None or costumer_client_id is not None
        else None,
    )


def _patch_create_order_dependencies(monkeypatch, requests):
    dummy_session = _DummySession()
    monkeypatch.setattr(module, "db", SimpleNamespace(session=dummy_session))
    monkeypatch.setattr(module, "extract_fields", lambda _ctx: [{"idx": i} for i in range(len(requests))])
    monkeypatch.setattr(module, "parse_create_order_request", lambda raw: requests[raw["idx"]])
    monkeypatch.setattr(module, "_load_delivery_plans_by_id", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(module, "build_order_created_event", lambda order: {"order_id": order.id})
    monkeypatch.setattr(module, "emit_order_events", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        module,
        "serialize_created_order",
        lambda order: {
            "id": order.id,
            "client_id": order.client_id,
            "costumer_id": order.costumer_id,
        },
    )
    monkeypatch.setattr(module, "serialize_created_items", lambda _items: [])
    monkeypatch.setattr(
        module,
        "reserve_order_scalar_ids",
        lambda _ctx, count: list(range(1, count + 1)),
    )

    def _create_instance(_ctx, model, fields):
        if model is module.Order:
            return SimpleNamespace(
                id=len(dummy_session.added) + 1,
                client_id=fields["client_id"],
                items=[],
                delivery_windows=[],
                delivery_plan_id=None,
                costumer_id=None,
                tracking_token_hash=None,
                items_updated_at=None,
            )
        return SimpleNamespace(client_id=fields.get("client_id", "item"))

    monkeypatch.setattr(module, "create_instance", _create_instance)
    return dummy_session


def _build_ctx():
    return SimpleNamespace(
        set_relationship_map=lambda *_args, **_kwargs: None,
        team_id=None,
        identity={},
    )


def test_create_order_links_costumer_ids_in_created_bundles(monkeypatch):
    requests = [
        _build_request(client_id="order_1", costumer_id=None, email="one@mail.com"),
        _build_request(client_id="order_2", costumer_id=None, email="two@mail.com"),
    ]
    _patch_create_order_dependencies(monkeypatch, requests)

    resolver_calls = {"count": 0}

    def _resolve(_ctx, _inputs):
        resolver_calls["count"] += 1
        return [SimpleNamespace(id=101), SimpleNamespace(id=102)]

    monkeypatch.setattr(module, "resolve_or_create_costumers", _resolve)

    result = module.create_order(_build_ctx())

    assert resolver_calls["count"] == 1
    assert result["created"][0]["order"]["costumer_id"] == 101
    assert result["created"][1]["order"]["costumer_id"] == 102


def test_create_order_passes_explicit_costumer_id_to_resolver(monkeypatch):
    requests = [_build_request(client_id="order_1", costumer_id=88, email="explicit@mail.com")]
    _patch_create_order_dependencies(monkeypatch, requests)
    captured = {}

    def _resolve(_ctx, inputs):
        captured["inputs"] = inputs
        return [SimpleNamespace(id=88)]

    monkeypatch.setattr(module, "resolve_or_create_costumers", _resolve)

    module.create_order(_build_ctx())

    assert captured["inputs"][0].costumer_id == 88
    assert captured["inputs"][0].costumer_client_id is None
    assert captured["inputs"][0].email == "explicit@mail.com"


def test_create_order_fallback_input_uses_order_snapshot_fields(monkeypatch):
    request = OrderCreateRequest(
        fields={
            "client_id": "order_1",
            "client_first_name": "Martha",
            "client_last_name": "Jensen",
            "client_email": "martha@mail.com",
            "client_primary_phone": {"prefix": "+1", "number": "555"},
            "client_address": {"street_address": "Main 1"},
        },
        items=[],
        route_plan_id=None,
        costumer=None,
    )
    _patch_create_order_dependencies(monkeypatch, [request])
    captured = {}

    def _resolve(_ctx, inputs):
        captured["input"] = inputs[0]
        return [SimpleNamespace(id=201)]

    monkeypatch.setattr(module, "resolve_or_create_costumers", _resolve)

    module.create_order(_build_ctx())

    assert captured["input"].costumer_id is None
    assert captured["input"].first_name == "Martha"
    assert captured["input"].last_name == "Jensen"
    assert captured["input"].email == "martha@mail.com"
    assert captured["input"].primary_phone == {"prefix": "+1", "number": "555"}
    assert captured["input"].address == {"street_address": "Main 1"}


def test_create_order_prefers_nested_costumer_defaults(monkeypatch):
    request = OrderCreateRequest(
        fields={
            "client_id": "order_1",
            "client_first_name": "OrderName",
            "client_last_name": "OrderLast",
            "client_email": "order@mail.com",
            "client_primary_phone": {"prefix": "+1", "number": "111"},
            "client_address": {"street_address": "Order St"},
        },
        items=[],
        route_plan_id=None,
        costumer=OrderCostumerRequest(
            costumer_id=None,
            client_id="costumer_front_client",
            first_name="CostumerName",
            last_name="CostumerLast",
            email="costumer@mail.com",
            primary_phone={"prefix": "+46", "number": "700"},
            address={"street_address": "Costumer St"},
        ),
    )
    _patch_create_order_dependencies(monkeypatch, [request])
    captured = {}

    def _resolve(_ctx, inputs):
        captured["input"] = inputs[0]
        return [SimpleNamespace(id=301)]

    monkeypatch.setattr(module, "resolve_or_create_costumers", _resolve)

    module.create_order(_build_ctx())

    assert captured["input"].costumer_id is None
    assert captured["input"].costumer_client_id == "costumer_front_client"
    assert captured["input"].first_name == "CostumerName"
    assert captured["input"].last_name == "CostumerLast"
    assert captured["input"].email == "costumer@mail.com"
    assert captured["input"].primary_phone == {"prefix": "+46", "number": "700"}
    assert captured["input"].address == {"street_address": "Costumer St"}


def test_create_order_calls_batch_resolver_once_for_many_orders(monkeypatch):
    requests = [
        _build_request(client_id="order_1", costumer_id=None, email="one@mail.com"),
        _build_request(client_id="order_2", costumer_id=None, email="two@mail.com"),
        _build_request(client_id="order_3", costumer_id=None, email="three@mail.com"),
    ]
    _patch_create_order_dependencies(monkeypatch, requests)
    resolver_calls = {"count": 0}

    def _resolve(_ctx, _inputs):
        resolver_calls["count"] += 1
        return [SimpleNamespace(id=1), SimpleNamespace(id=2), SimpleNamespace(id=3)]

    monkeypatch.setattr(module, "resolve_or_create_costumers", _resolve)

    module.create_order(_build_ctx())

    assert resolver_calls["count"] == 1
