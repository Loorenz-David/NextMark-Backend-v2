from Delivery_app_BK.services.commands.test_data.processors import route_plan as module
from Delivery_app_BK.services.commands.test_data.registry import Registry


def test_auto_registers_default_route_group(monkeypatch):
    monkeypatch.setattr(
        module,
        "create_plan",
        lambda ctx: {
            "created": [
                {
                    "delivery_plan": {"id": 91},
                    "route_groups": [{"id": 1001}],
                }
            ]
        },
    )
    registry = Registry()

    result = module.process(
        {"label": "Plan", "_sid": "p1"},
        {"team_id": 5, "user_id": 1},
        registry,
    )

    assert result == 91
    assert registry.resolve("p1.rg.default") == 1001


def test_auto_registers_zone_route_groups(monkeypatch):
    monkeypatch.setattr(
        module,
        "create_plan",
        lambda ctx: {
            "created": [
                {
                    "delivery_plan": {"id": 91},
                    "route_groups": [{"id": 1001}, {"id": 1002}, {"id": 1003}],
                }
            ]
        },
    )
    registry = Registry()

    module.process(
        {"label": "Plan", "zone_ids": [11, 12], "_sid": "p1", "_zone_sids": ["z1", "z2"]},
        {"team_id": 5, "user_id": 1},
        registry,
    )

    assert registry.resolve("p1.rg.z1") == 1002
    assert registry.resolve("p1.rg.z2") == 1003


def test_strips_internal_metadata_from_plan_fields(monkeypatch):
    calls = []

    def fake_create_plan(ctx):
        calls.append(ctx.incoming_data)
        return {"created": [{"delivery_plan": {"id": 91}, "route_groups": [{"id": 1001}]}]}

    monkeypatch.setattr(module, "create_plan", fake_create_plan)

    module.process(
        {"label": "Plan", "_sid": "p1", "_zone_sids": ["z1"]},
        {"team_id": 5, "user_id": 1},
        Registry(),
    )

    assert calls == [{"fields": [{"label": "Plan"}]}]


def test_strips_unknown_fields_from_plan_fields(monkeypatch):
    calls = []

    def fake_create_plan(ctx):
        calls.append(ctx.incoming_data)
        return {"created": [{"delivery_plan": {"id": 91}, "route_groups": [{"id": 1001}]}]}

    monkeypatch.setattr(module, "create_plan", fake_create_plan)

    module.process(
        {"label": "Plan", "zone_ids": [11], "plan_type": "ignored", "state_id": 2},
        {"team_id": 5, "user_id": 1},
        Registry(),
    )

    assert calls == [{"fields": [{"label": "Plan", "zone_ids": [11]}]}]


def test_only_registers_if_sid_provided(monkeypatch):
    monkeypatch.setattr(
        module,
        "create_plan",
        lambda ctx: {
            "created": [
                {
                    "delivery_plan": {"id": 91},
                    "route_groups": [{"id": 1001}, {"id": 1002}],
                }
            ]
        },
    )
    registry = Registry()

    module.process(
        {"label": "Plan", "zone_ids": [11], "_zone_sids": ["z1"]},
        {"team_id": 5, "user_id": 1},
        registry,
    )

    assert registry.is_registered("p1.rg.default") is False
