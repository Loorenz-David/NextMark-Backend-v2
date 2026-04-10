from Delivery_app_BK.services.commands.test_data.processors import zone_template as module


def test_process_calls_service_and_returns_id(monkeypatch):
    calls = []

    def fake_create_zone_template(ctx):
        calls.append(ctx.incoming_data)
        return {"id": 53}

    monkeypatch.setattr(module, "create_zone_template", fake_create_zone_template)

    result = module.process(
        {"zone_id": 10, "default_facility_id": 20, "name": "Template"},
        {"team_id": 5, "user_id": 1},
        None,
    )

    assert result == 53
    assert calls == [{"zone_id": 10, "default_facility_id": 20, "name": "Template"}]
