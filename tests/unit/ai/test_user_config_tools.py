from Delivery_app_BK.ai.tools import user_config_tools
from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.services.context import ServiceContext


def test_list_item_types_config_tool_passes_filters(monkeypatch):
    captured = {}

    def _fake_list_item_types_service(ctx):
        captured["query_params"] = dict(ctx.query_params)
        return {
            "item_types": [{"id": 1, "name": "table", "properties": [11, 12]}],
            "item_types_pagination": {"has_more": False},
        }

    monkeypatch.setattr(user_config_tools, "list_item_types_service", _fake_list_item_types_service)

    ctx = ServiceContext(query_params={"existing": "keep"})
    result = user_config_tools.list_item_types_config_tool(ctx, name="tab", limit=20, sort="id_asc")

    assert captured["query_params"]["existing"] == "keep"
    assert captured["query_params"]["name"] == "tab"
    assert captured["query_params"]["limit"] == 20
    assert captured["query_params"]["sort"] == "id_asc"
    assert result["count"] == 1
    assert result["item_types"][0]["name"] == "table"


def test_link_properties_to_item_type_tool_merges_existing_ids(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        user_config_tools,
        "get_item_type_service",
        lambda item_type_id, ctx: {"item_type": {"id": item_type_id, "properties": [10, 11]}},
    )

    def _fake_update_item_type_config_tool(ctx, item_type_id, fields):
        captured["item_type_id"] = item_type_id
        captured["fields"] = fields
        return {"status": "updated"}

    monkeypatch.setattr(user_config_tools, "update_item_type_config_tool", _fake_update_item_type_config_tool)

    ctx = ServiceContext()
    result = user_config_tools.link_properties_to_item_type_tool(ctx, item_type_id=5, property_ids=[11, 12], merge=True)

    assert captured["item_type_id"] == 5
    assert captured["fields"]["properties"] == [10, 11, 12]
    assert result["status"] == "updated"


def test_create_item_property_config_tool_builds_fields(monkeypatch):
    captured = {}

    def _fake_create_item_property_service(ctx):
        captured["incoming_data"] = dict(ctx.incoming_data)
        return {
            "item_property": [
                {
                    "id": 7,
                    "name": "material",
                    "field_type": "select",
                    "options": ["oak", "pine"],
                    "required": True,
                }
            ]
        }

    monkeypatch.setattr(user_config_tools, "create_item_property_service", _fake_create_item_property_service)

    ctx = ServiceContext()
    result = user_config_tools.create_item_property_config_tool(
        ctx,
        name="material",
        field_type="select",
        required=True,
        options=["oak", "pine"],
        item_type_ids=[1, 2],
    )

    fields = captured["incoming_data"]["fields"]
    assert fields["name"] == "material"
    assert fields["field_type"] == "select"
    assert fields["required"] is True
    assert fields["options"] == ["oak", "pine"]
    assert fields["item_types"] == [1, 2]
    assert result["status"] == "created"
    assert result["item_property"]["id"] == 7


def test_create_item_taxonomy_proposal_tool_returns_token_and_summary():
    ctx = ServiceContext()

    result = user_config_tools.create_item_taxonomy_proposal_tool(
        ctx,
        item_types=[
            {
                "name": "Furniture",
                "properties": [
                    {"name": "Material", "field_type": "select", "required": True, "options": ["oak", "pine"]},
                    {"name": "Weight", "field_type": "number"},
                ],
            }
        ],
        proposal_name="furniture-v1",
    )

    assert result["status"] == "proposal_ready"
    assert result["requires_approval"] is True
    assert result["approval_token"].startswith("tax_")
    assert result["summary"]["item_types_count"] == 1
    assert result["summary"]["properties_count"] == 2
    assert result["proposal"]["meta"]["status"] == "pending_confirm"
    assert isinstance(result["proposal"]["meta"]["created_at"], str)
    assert isinstance(result["proposal"]["meta"]["expires_at"], str)


def test_apply_item_taxonomy_proposal_tool_requires_approval():
    ctx = ServiceContext()
    proposal = {"item_types": [{"name": "Furniture", "properties": []}]}

    try:
        user_config_tools.apply_item_taxonomy_proposal_tool(
            ctx,
            proposal=proposal,
            approval_token="tax_invalid",
            approved=False,
        )
    except ValidationFailed as exc:
        assert "approved=true" in str(exc)
    else:
        raise AssertionError("Expected ValidationFailed when approved is false")


def test_apply_item_taxonomy_proposal_tool_creates_missing_and_reuses_existing(monkeypatch):
    user_config_tools._APPLIED_PROPOSAL_HASHES.clear()
    created_properties = []
    created_types = []
    linked_types = []

    monkeypatch.setattr(
        user_config_tools,
        "_find_item_property_by_name",
        lambda ctx, name: {"id": 11, "name": "material"} if name.lower() == "material" else None,
    )
    monkeypatch.setattr(
        user_config_tools,
        "_find_item_type_by_name",
        lambda ctx, name: None,
    )

    def _fake_create_item_property_config_tool(ctx, name, field_type="text", required=False, options=None, item_type_ids=None):
        created_properties.append(name)
        return {"item_property": {"id": 77, "name": name}}

    def _fake_create_item_type_config_tool(ctx, name, property_ids=None):
        created_types.append(name)
        return {"item_type": {"id": 88, "name": name}}

    def _fake_link_properties_to_item_type_tool(ctx, item_type_id, property_ids, merge=True):
        linked_types.append((item_type_id, list(property_ids), merge))
        return {"status": "updated"}

    monkeypatch.setattr(user_config_tools, "create_item_property_config_tool", _fake_create_item_property_config_tool)
    monkeypatch.setattr(user_config_tools, "create_item_type_config_tool", _fake_create_item_type_config_tool)
    monkeypatch.setattr(user_config_tools, "link_properties_to_item_type_tool", _fake_link_properties_to_item_type_tool)

    proposal_result = user_config_tools.create_item_taxonomy_proposal_tool(
        ServiceContext(),
        item_types=[
            {
                "name": "Furniture",
                "properties": [
                    {"name": "Material", "field_type": "select", "required": True, "options": ["oak"]},
                    {"name": "Color", "field_type": "text"},
                ],
            }
        ],
    )

    result = user_config_tools.apply_item_taxonomy_proposal_tool(
        ServiceContext(),
        proposal=proposal_result["proposal"],
        approval_token=proposal_result["approval_token"],
        approved=True,
    )

    assert result["status"] == "applied"
    assert result["created_item_types"] == 1
    assert result["reused_item_types"] == 0
    assert result["created_properties"] == 1
    assert result["reused_properties"] == 1
    assert result["proposal_meta"]["status"] == "applied"
    assert isinstance(result["proposal_meta"]["applied_at"], str)
    assert created_properties == ["Color"]
    assert created_types == ["Furniture"]
    assert linked_types == [(88, [11, 77], True)]


def test_apply_item_taxonomy_proposal_tool_rejects_duplicate_apply(monkeypatch):
    user_config_tools._APPLIED_PROPOSAL_HASHES.clear()
    user_config_tools._PROPOSAL_METRICS_COUNTERS.clear()

    monkeypatch.setattr(user_config_tools, "_find_item_property_by_name", lambda ctx, name: None)
    monkeypatch.setattr(user_config_tools, "_find_item_type_by_name", lambda ctx, name: None)
    monkeypatch.setattr(
        user_config_tools,
        "create_item_property_config_tool",
        lambda ctx, **kwargs: {"item_property": {"id": 1, "name": kwargs["name"]}},
    )
    monkeypatch.setattr(
        user_config_tools,
        "create_item_type_config_tool",
        lambda ctx, **kwargs: {"item_type": {"id": 2, "name": kwargs["name"]}},
    )
    monkeypatch.setattr(user_config_tools, "link_properties_to_item_type_tool", lambda *args, **kwargs: {"status": "updated"})

    proposal_result = user_config_tools.create_item_taxonomy_proposal_tool(
        ServiceContext(),
        item_types=[{"name": "Cabinet", "properties": [{"name": "Material"}]}],
    )

    user_config_tools.apply_item_taxonomy_proposal_tool(
        ServiceContext(),
        proposal=proposal_result["proposal"],
        approval_token=proposal_result["approval_token"],
        approved=True,
    )

    try:
        user_config_tools.apply_item_taxonomy_proposal_tool(
            ServiceContext(),
            proposal=proposal_result["proposal"],
            approval_token=proposal_result["approval_token"],
            approved=True,
        )
    except ValidationFailed as exc:
        assert "already been applied" in str(exc)
        assert getattr(exc, "code", None) == "proposal_already_applied"
    else:
        raise AssertionError("Expected ValidationFailed on duplicate proposal apply")


def test_apply_item_taxonomy_proposal_tool_rejects_expired_proposal(monkeypatch):
    proposal = {
        "proposal_name": "old",
        "item_types": [{"name": "Cabinet", "properties": []}],
        "meta": {
            "status": "pending_confirm",
            "created_at": "2026-01-01T00:00:00Z",
            "expires_at": "2026-01-02T00:00:00Z",
            "version": 1,
        },
    }
    token = user_config_tools._build_proposal_token(proposal)

    monkeypatch.setattr(user_config_tools, "_utcnow", lambda: user_config_tools._parse_utc_iso("2026-02-01T00:00:00Z"))

    try:
        user_config_tools.apply_item_taxonomy_proposal_tool(
            ServiceContext(),
            proposal=proposal,
            approval_token=token,
            approved=True,
        )
    except ValidationFailed as exc:
        assert "expired" in str(exc)
        assert getattr(exc, "code", None) == "proposal_expired"
    else:
        raise AssertionError("Expected ValidationFailed for expired proposal")


def test_apply_item_taxonomy_proposal_tool_rejects_invalid_status_transition():
    proposal = {
        "proposal_name": "cancelled",
        "item_types": [{"name": "Cabinet", "properties": []}],
        "meta": {
            "status": "cancelled",
            "created_at": "2026-01-01T00:00:00Z",
            "expires_at": "2026-06-01T00:00:00Z",
            "version": 1,
        },
    }
    token = user_config_tools._build_proposal_token(proposal)

    try:
        user_config_tools.apply_item_taxonomy_proposal_tool(
            ServiceContext(),
            proposal=proposal,
            approval_token=token,
            approved=True,
        )
    except ValidationFailed as exc:
        assert "cancelled" in str(exc)
        assert getattr(exc, "code", None) == "proposal_cancelled"
    else:
        raise AssertionError("Expected ValidationFailed for cancelled proposal")


def test_apply_item_taxonomy_proposal_tool_rejects_conflicting_token():
    proposal = {
        "proposal_name": "conflict",
        "item_types": [{"name": "Cabinet", "properties": []}],
        "meta": {
            "status": "pending_confirm",
            "created_at": "2026-01-01T00:00:00Z",
            "expires_at": "2026-06-01T00:00:00Z",
            "version": 1,
        },
    }

    try:
        user_config_tools.apply_item_taxonomy_proposal_tool(
            ServiceContext(),
            proposal=proposal,
            approval_token="tax_wrong",
            approved=True,
        )
    except ValidationFailed as exc:
        assert "approval_token" in str(exc)
        assert getattr(exc, "code", None) == "proposal_conflict"
    else:
        raise AssertionError("Expected ValidationFailed for conflicting approval token")


def test_proposal_metrics_counters_track_apply_success_and_failure(monkeypatch):
    user_config_tools._APPLIED_PROPOSAL_HASHES.clear()
    user_config_tools._PROPOSAL_METRICS_COUNTERS.clear()

    monkeypatch.setattr(user_config_tools, "_find_item_property_by_name", lambda ctx, name: None)
    monkeypatch.setattr(user_config_tools, "_find_item_type_by_name", lambda ctx, name: None)
    monkeypatch.setattr(
        user_config_tools,
        "create_item_property_config_tool",
        lambda ctx, **kwargs: {"item_property": {"id": 1, "name": kwargs["name"]}},
    )
    monkeypatch.setattr(
        user_config_tools,
        "create_item_type_config_tool",
        lambda ctx, **kwargs: {"item_type": {"id": 2, "name": kwargs["name"]}},
    )
    monkeypatch.setattr(user_config_tools, "link_properties_to_item_type_tool", lambda *args, **kwargs: {"status": "updated"})

    proposal_result = user_config_tools.create_item_taxonomy_proposal_tool(
        ServiceContext(),
        item_types=[{"name": "Cabinet", "properties": [{"name": "Material"}]}],
    )

    user_config_tools.apply_item_taxonomy_proposal_tool(
        ServiceContext(),
        proposal=proposal_result["proposal"],
        approval_token=proposal_result["approval_token"],
        approved=True,
    )

    try:
        user_config_tools.apply_item_taxonomy_proposal_tool(
            ServiceContext(),
            proposal=proposal_result["proposal"],
            approval_token=proposal_result["approval_token"],
            approved=True,
        )
    except ValidationFailed:
        pass

    metrics = user_config_tools.get_proposal_metrics_snapshot()
    assert metrics["ai_proposal_create|outcome=success|error_code=none"] >= 1
    assert metrics["ai_proposal_apply|outcome=success|error_code=none"] >= 1
    assert metrics["ai_proposal_apply|outcome=failure|error_code=proposal_already_applied"] >= 1


def test_mark_proposal_applied_once_uses_redis_atomic_set(monkeypatch):
    class _FakeRedis:
        def __init__(self):
            self.claimed = set()

        def set(self, key, value, nx=False, ex=None):
            if not nx:
                return True
            if key in self.claimed:
                return None
            self.claimed.add(key)
            return True

    fake_redis = _FakeRedis()
    monkeypatch.setattr(user_config_tools, "get_current_redis_connection", lambda: fake_redis)
    monkeypatch.setattr(user_config_tools, "build_ai_proposal_apply_key", lambda proposal_hash: f"k:{proposal_hash}")

    assert user_config_tools._mark_proposal_applied_once("hash_1") is True
    assert user_config_tools._mark_proposal_applied_once("hash_1") is False


def test_mark_proposal_applied_once_fallbacks_without_redis(monkeypatch):
    user_config_tools._APPLIED_PROPOSAL_HASHES.clear()
    monkeypatch.setattr(
        user_config_tools,
        "get_current_redis_connection",
        lambda: (_ for _ in ()).throw(RuntimeError("redis unavailable")),
    )

    assert user_config_tools._mark_proposal_applied_once("hash_2") is True
    assert user_config_tools._mark_proposal_applied_once("hash_2") is False