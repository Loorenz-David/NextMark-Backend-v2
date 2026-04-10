from types import SimpleNamespace

from Delivery_app_BK.services.commands.test_data.processors import item_type as module


def test_process_calls_create_item_type_with_resolved_properties(monkeypatch):
    calls = []

    def fake_create_item_type(ctx):
        calls.append(ctx.incoming_data)
        return [SimpleNamespace(id=66)]

    monkeypatch.setattr(module, "create_item_type", fake_create_item_type)

    result = module.process(
        {"name": "test-Chair", "properties": [101, 102]},
        {"team_id": 5, "user_id": 1},
        None,
    )

    assert result == 66
    assert calls == [{"fields": [{"name": "test-Chair", "properties": [101, 102]}]}]


def test_process_returns_db_id(monkeypatch):
    monkeypatch.setattr(module, "create_item_type", lambda ctx: [SimpleNamespace(id=66)])

    assert module.process({"name": "test-Chair"}, {"team_id": 5, "user_id": 1}, None) == 66


def test_process_with_no_properties(monkeypatch):
    calls = []

    def fake_create_item_type(ctx):
        calls.append(ctx.incoming_data)
        return [SimpleNamespace(id=66)]

    monkeypatch.setattr(module, "create_item_type", fake_create_item_type)

    module.process(
        {"name": "test-Chair", "properties": []},
        {"team_id": 5, "user_id": 1},
        None,
    )

    assert calls == [{"fields": [{"name": "test-Chair", "properties": []}]}]
