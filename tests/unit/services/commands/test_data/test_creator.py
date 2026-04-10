import pytest

from Delivery_app_BK.services.commands.test_data import creator as module


def test_processes_entities_in_topological_order(monkeypatch):
    calls: list[str] = []

    def fake_process(name, return_id):
        def _process(item, identity, registry):
            calls.append(name)
            return return_id
        return _process

    monkeypatch.setattr(
        module,
        "PROCESSOR_MAP",
        {
            "item_property": fake_process("item_property", 1),
            "item_type": fake_process("item_type", 2),
            "facility": fake_process("facility", 3),
            "vehicle": fake_process("vehicle", 4),
            "zone_version": fake_process("zone_version", 5),
            "zone": fake_process("zone", 6),
            "zone_template": fake_process("zone_template", 7),
            "route_plan": fake_process("route_plan", 8),
            "order": fake_process("order", 9),
            "order_delivery_window": fake_process("order_delivery_window", 10),
            "order_zone_assignment": fake_process("order_zone_assignment", 11),
        },
    )

    payload = {
        "vehicle": [{"label": "Van", "registration_number": "ABC-001"}],
        "item_property": [{"name": "Color"}],
        "order": [{"reference_number": "test-001"}],
        "zone_template": [{"name": "Template"}],
        "facility": [{"name": "Depot"}],
        "item_type": [{"name": "Chair"}],
        "zone": [{"name": "North"}],
        "zone_version": [{"city_key": "stockholm"}],
        "route_plan": [{"label": "Plan"}],
    }

    module.create_test_data({"team_id": 5, "user_id": 1}, payload)

    assert calls == [
        "item_property",
        "item_type",
        "facility",
        "vehicle",
        "zone_version",
        "zone",
        "zone_template",
        "route_plan",
        "order",
    ]


def test_skips_missing_entity_keys(monkeypatch):
    calls: list[str] = []

    def fake_process(item, identity, registry):
        calls.append("facility")
        return 101

    monkeypatch.setitem(module.PROCESSOR_MAP, "facility", fake_process)

    result = module.create_test_data({"team_id": 5, "user_id": 1}, {"facility": [{"name": "Depot"}]})

    assert calls == ["facility"]
    assert result == {"facility": {"count": 1, "ids": [101]}}


def test_registers_sid_after_create(monkeypatch):
    def facility_process(item, identity, registry):
        assert item["client_id"].startswith("td:facility:f1:")
        return 101

    calls: list[dict] = []

    def vehicle_process(item, identity, registry):
        calls.append(item)
        return 202

    monkeypatch.setitem(module.PROCESSOR_MAP, "facility", facility_process)
    monkeypatch.setitem(module.PROCESSOR_MAP, "vehicle", vehicle_process)

    module.create_test_data(
        {"team_id": 5, "user_id": 1},
        {
            "facility": [{"$id": "f1", "name": "Depot"}],
            "vehicle": [{"$facility": "f1", "label": "Van", "registration_number": "ABC-001"}],
        },
    )

    assert calls[0]["home_facility_id"] == 101
    assert calls[0]["label"] == "Van"
    assert calls[0]["registration_number"] == "ABC-001"
    assert calls[0]["client_id"].startswith("td:vehicle:")


def test_returns_count_and_ids(monkeypatch):
    next_id = iter([101, 102])

    def facility_process(item, identity, registry):
        return next(next_id)

    monkeypatch.setitem(module.PROCESSOR_MAP, "facility", facility_process)

    result = module.create_test_data(
        {"team_id": 5, "user_id": 1},
        {"facility": [{"name": "A"}, {"name": "B"}]},
    )

    assert result == {"facility": {"count": 2, "ids": [101, 102]}}


def test_route_plan_receives_zone_sids(monkeypatch):
    captured: list[dict] = []

    def zone_process(item, identity, registry):
        return 501 if item["name"] == "North" else 502

    def route_plan_process(item, identity, registry):
        captured.append(item)
        return 601

    monkeypatch.setitem(module.PROCESSOR_MAP, "zone", zone_process)
    monkeypatch.setitem(module.PROCESSOR_MAP, "route_plan", route_plan_process)

    module.create_test_data(
        {"team_id": 5, "user_id": 1},
        {
            "zone": [
                {"$id": "z1", "name": "North"},
                {"$id": "z2", "name": "South"},
            ],
            "route_plan": [
                {"$id": "p1", "$zones": ["z1", "z2"], "label": "Plan"}
            ],
        },
    )

    assert captured == [
        {
            "zone_ids": [501, 502],
            "label": "Plan",
            "client_id": captured[0]["client_id"],
            "_sid": "p1",
            "_zone_sids": ["z1", "z2"],
        }
    ]
    assert captured[0]["client_id"].startswith("td:route_plan:p1:")


def test_rejects_non_list_entity_value():
    with pytest.raises(ValueError):
        module.create_test_data({"team_id": 5, "user_id": 1}, {"facility": {}})


def test_rejects_unknown_entity_key():
    with pytest.raises(ValueError, match="Unknown entity keys"):
        module.create_test_data(
            {"team_id": 5, "user_id": 1},
            {"unknown_entity": [{}]},
        )


def test_meta_client_id_prefix_overrides_default(monkeypatch):
    captured: list[dict] = []

    def facility_process(item, identity, registry):
        captured.append(item)
        return 101

    monkeypatch.setitem(module.PROCESSOR_MAP, "facility", facility_process)

    module.create_test_data(
        {"team_id": 5, "user_id": 1},
        {
            "_meta": {"client_id_prefix": "marker:"},
            "facility": [{"$id": "f1", "name": "Depot"}],
        },
    )

    assert captured[0]["client_id"].startswith("marker:facility:f1:")
