from Delivery_app_BK.services.commands.test_data.processors import zone_version as module


def test_process_calls_service_and_returns_id(monkeypatch):
    calls = []

    def fake_create_zone_version(ctx):
        calls.append(ctx.incoming_data)
        return {"id": 51}

    monkeypatch.setattr(module, "create_zone_version", fake_create_zone_version)

    result = module.process({"city_key": "stockholm"}, {"team_id": 5, "user_id": 1}, None)

    assert result == 51
    assert calls == [{"city_key": "stockholm"}]
