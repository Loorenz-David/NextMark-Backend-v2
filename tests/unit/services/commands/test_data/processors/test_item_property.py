from types import SimpleNamespace

from Delivery_app_BK.services.commands.test_data.processors import item_property as module


def test_process_calls_create_item_property_with_fields_wrapper(monkeypatch):
    calls = []

    def fake_create_item_property(ctx):
        calls.append(ctx.incoming_data)
        return [SimpleNamespace(id=55)]

    monkeypatch.setattr(module, "create_item_property", fake_create_item_property)

    result = module.process({"name": "test-Color"}, {"team_id": 5, "user_id": 1}, None)

    assert result == 55
    assert calls == [{"fields": [{"name": "test-Color", "required": False}]}]


def test_process_returns_db_id(monkeypatch):
    monkeypatch.setattr(
        module,
        "create_item_property",
        lambda ctx: [SimpleNamespace(id=55)],
    )

    assert module.process({"name": "test-Color"}, {"team_id": 5, "user_id": 1}, None) == 55


def test_process_strips_underscore_keys(monkeypatch):
    calls = []

    def fake_create_item_property(ctx):
        calls.append(ctx.incoming_data)
        return [SimpleNamespace(id=55)]

    monkeypatch.setattr(module, "create_item_property", fake_create_item_property)

    module.process(
        {"name": "test-Color", "_sid": "ip1"},
        {"team_id": 5, "user_id": 1},
        None,
    )

    assert calls == [{"fields": [{"name": "test-Color", "required": False}]}]


def test_process_defaults_required_to_false_if_omitted(monkeypatch):
    calls = []

    def fake_create_item_property(ctx):
        calls.append(ctx.incoming_data["fields"][0])
        return [SimpleNamespace(id=55)]

    monkeypatch.setattr(module, "create_item_property", fake_create_item_property)

    module.process(
        {"name": "test-Color", "field_type": "text"},
        {"team_id": 5, "user_id": 1},
        None,
    )

    assert calls[0]["required"] is False
