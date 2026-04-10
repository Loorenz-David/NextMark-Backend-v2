from types import SimpleNamespace

from Delivery_app_BK.services.commands.test_data.processors import order_zone_assignment as module


def test_process_calls_service_and_returns_id(monkeypatch):
    def fake_create_instance(ctx, model, fields):
        return SimpleNamespace(id=82)

    monkeypatch.setattr(module, "create_instance", fake_create_instance)
    monkeypatch.setattr(module.db.session, "add", lambda instance: None)
    monkeypatch.setattr(module.db.session, "flush", lambda: None)

    result = module.process(
        {"order_id": 10, "zone_id": 20, "zone_version_id": 30, "city_key": "stockholm"},
        {"team_id": 5, "user_id": 1},
        None,
    )

    assert result == 82
