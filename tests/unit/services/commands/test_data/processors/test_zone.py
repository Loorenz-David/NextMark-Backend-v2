from Delivery_app_BK.services.commands.test_data.processors import zone as module


def test_process_calls_service_and_returns_id(monkeypatch):
    calls = []

    def fake_create_zone(ctx):
        calls.append(ctx.incoming_data)
        return {"id": 52}

    monkeypatch.setattr(module, "create_zone", fake_create_zone)

    result = module.process(
        {"version_id": 7, "name": "North", "zone_type": "user"},
        {"team_id": 5, "user_id": 1},
        None,
    )

    assert result == 52
    assert calls == [{"version_id": 7, "name": "North", "zone_type": "user"}]
