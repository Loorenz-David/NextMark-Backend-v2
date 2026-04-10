from Delivery_app_BK.services.context import ServiceContext
from Delivery_app_BK.services.queries.bootstrap import list_bootstrap as module


def _patch_non_zone_bootstrap_dependencies(monkeypatch):
    monkeypatch.setattr(module, "list_team_members", lambda _ctx: {"team_members": []})
    monkeypatch.setattr(module, "list_item_states", lambda _ctx: {"item_states": []})
    monkeypatch.setattr(module, "list_order_states", lambda _ctx: {"order_states": []})
    monkeypatch.setattr(module, "list_plan_states", lambda _ctx: {"plan_states": []})
    monkeypatch.setattr(module, "list_label_templates_bootstrap", lambda _ctx: {"label_templates": []})
    monkeypatch.setattr(module, "list_vehicles", lambda _ctx: {"vehicles": []})
    monkeypatch.setattr(module, "list_message_templates_bootstrap", lambda _ctx: {"message_templates": []})


def test_list_bootstrap_zones_uses_explicit_city_key_override(monkeypatch):
    _patch_non_zone_bootstrap_dependencies(monkeypatch)

    def _fake_versions(ctx):
        assert ctx.query_params["city_key"] == "gothenburg"
        return [
            {"id": 10, "is_active": False, "city_key": "gothenburg", "version_number": 1},
            {"id": 11, "is_active": True, "city_key": "gothenburg", "version_number": 2},
        ]

    def _fake_zones(ctx):
        assert ctx.query_params["version_id"] == 11
        return [
            {
                "id": 101,
                "name": "North",
                "zone_type": "system",
                "centroid_lat": 59.35,
                "centroid_lng": 18.06,
                "geometry": {"type": "Polygon", "coordinates": []},
                "min_lat": 59.35,
                "max_lat": 59.39,
                "min_lng": 18.01,
                "max_lng": 18.08,
                "is_active": True,
                "template": {
                    "id": 501,
                    "name": "Default Template",
                    "version": 3,
                    "config_json": {"max_stops": 20},
                },
            }
        ]

    monkeypatch.setattr(module, "list_zone_versions", _fake_versions)
    monkeypatch.setattr(module, "list_zones_for_version", _fake_zones)

    ctx = ServiceContext(
        query_params={"city_key": "Gothenburg"},
        identity={"active_team_id": 1, "default_city_key": "stockholm"},
    )

    payload = module.list_bootstrap(ctx)

    assert payload["zones_context"]["city_key"] == "gothenburg"
    assert payload["zones_context"]["selected_version"] == {
        "id": 11,
        "version_number": 2,
        "is_active": True,
    }
    zone = payload["zones_context"]["zones"][0]
    assert zone["id"] == 101
    assert zone["centroid"] == {"lat": 59.35, "lng": 18.06}
    assert zone["bbox"] == {
        "min_lat": 59.35,
        "max_lat": 59.39,
        "min_lng": 18.01,
        "max_lng": 18.08,
    }
    assert zone["geometry_simplified"] == {"type": "Polygon", "coordinates": []}
    assert zone["template_ref"] == {"id": 501, "name": "Default Template", "version": 3}
    assert zone["has_geometry"] is True
    assert zone["geometry_resolution"] == "simplified"


def test_list_bootstrap_zones_falls_back_to_identity_city(monkeypatch):
    _patch_non_zone_bootstrap_dependencies(monkeypatch)

    monkeypatch.setattr(
        module,
        "list_zone_versions",
        lambda _ctx: [{"id": 5, "is_active": False, "city_key": "stockholm", "version_number": 1}],
    )
    monkeypatch.setattr(
        module,
        "list_zones_for_version",
        lambda _ctx: [
            {
                "id": 77,
                "name": "City",
                "zone_type": "user",
                "centroid_lat": None,
                "centroid_lng": None,
                "geometry": None,
                "min_lat": None,
                "max_lat": None,
                "min_lng": None,
                "max_lng": None,
                "is_active": True,
                "template": None,
            }
        ],
    )

    ctx = ServiceContext(
        query_params={},
        identity={"active_team_id": 1, "default_city_key": "stockholm"},
    )

    payload = module.list_bootstrap(ctx)

    assert payload["zones_context"]["city_key"] == "stockholm"
    assert payload["zones_context"]["selected_version"] == {
        "id": 5,
        "version_number": 1,
        "is_active": False,
    }
    zone = payload["zones_context"]["zones"][0]
    assert zone["id"] == 77
    assert zone["centroid"] is None
    assert zone["bbox"] is None
    assert zone["geometry_simplified"] is None
    assert zone["template_ref"] is None
    assert zone["has_geometry"] is False
    assert zone["geometry_resolution"] == "none"
    assert ctx.warnings == []


def test_list_bootstrap_zones_returns_empty_and_warning_without_city(monkeypatch):
    _patch_non_zone_bootstrap_dependencies(monkeypatch)

    versions_called = {"value": False}

    def _fake_versions(_ctx):
        versions_called["value"] = True
        return []

    monkeypatch.setattr(module, "list_zone_versions", _fake_versions)
    monkeypatch.setattr(module, "list_zones_for_version", lambda _ctx: [])

    ctx = ServiceContext(query_params={}, identity={"active_team_id": 1})

    payload = module.list_bootstrap(ctx)

    assert versions_called["value"] is False
    assert payload["zones_context"] == {
        "city_key": None,
        "selected_version": None,
        "zones": [],
    }
    assert len(ctx.warnings) == 1
