from types import SimpleNamespace

from Delivery_app_BK.services.commands.test_data.processors import facility as module


def test_process_calls_service_and_returns_id(monkeypatch):
    calls = []

    def fake_parse(payload):
        calls.append(payload)
        return SimpleNamespace(to_fields_dict=lambda: {"name": "Test", "team_id": 5})

    def fake_create_instance(ctx, model, fields):
        return SimpleNamespace(id=42)

    monkeypatch.setattr(module, "parse_create_facility_request", fake_parse)
    monkeypatch.setattr(module, "create_instance", fake_create_instance)
    monkeypatch.setattr(module.db.session, "add", lambda instance: None)
    monkeypatch.setattr(module.db.session, "flush", lambda: None)

    result = module.process({"name": "Test"}, {"team_id": 5, "user_id": 1}, None)

    assert result == 42
    assert calls == [{"name": "Test"}]
