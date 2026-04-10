from Delivery_app_BK.ai import model_selector, orchestrator, tool_executor
from Delivery_app_BK.ai.capabilities import get_capability_profile
from Delivery_app_BK.ai.capabilities.base import CapabilityProfile, ModelTarget
from Delivery_app_BK.ai.schemas import PlannerFinalStep, PlannerToolStep
from Delivery_app_BK.ai.stages import EXECUTE_STAGE
from Delivery_app_BK.services.context import ServiceContext


class _DummyProvider:
    name = "dummy"

    def complete(self, system: str, user: str) -> str:
        return ""


def test_logistics_capability_exposes_execute_prompt_and_tools():
    capability = get_capability_profile("logistics")

    prompt = capability.build_prompt(EXECUTE_STAGE)

    assert "AI logistics planner" in prompt
    assert "create_order" in capability.get_tools(EXECUTE_STAGE)


def test_select_provider_for_stage_uses_capability_model_target(monkeypatch):
    capability = CapabilityProfile(
        name="custom",
        description="custom",
        prompt_builders={EXECUTE_STAGE: lambda **_kw: "prompt"},
        stage_models={EXECUTE_STAGE: ModelTarget(provider_name="dummy", model_name="model-x")},
    )

    monkeypatch.setattr(model_selector, "get_capability_profile", lambda name: capability)
    monkeypatch.setitem(
        model_selector.PROVIDER_FACTORIES,
        "dummy",
        lambda model_name: {"provider": "dummy", "model": model_name},
    )

    provider = model_selector.select_provider_for_stage("custom", EXECUTE_STAGE)

    assert provider == {"provider": "dummy", "model": "model-x"}


def test_execute_tool_rejects_tool_outside_scoped_registry():
    try:
        tool_executor.execute_tool(None, "create_order", {}, allowed_tools={"list_orders": lambda ctx: {}})
    except ValueError as exc:
        assert "Allowed: ['list_orders']" in str(exc)
    else:
        raise AssertionError("execute_tool should reject tools outside the scoped registry")


def test_orchestrator_uses_capability_prompt_selector_and_scoped_tools(monkeypatch):
    captured = {}
    allowed_tools = {"echo_tool": lambda ctx, text: {"echo": text}}
    capability = CapabilityProfile(
        name="logistics",
        description="logistics",
        prompt_builders={EXECUTE_STAGE: lambda **_kw: "stage-prompt"},
        tool_registries={EXECUTE_STAGE: allowed_tools},
    )

    monkeypatch.setattr(orchestrator, "get_capability_profile", lambda name: capability)
    monkeypatch.setattr(orchestrator, "select_provider_for_stage", lambda capability_name, stage_name: _DummyProvider())

    steps = iter([
        PlannerToolStep(type="tool", tool="echo_tool", parameters={"text": "hello"}),
        PlannerFinalStep(type="final", message="ok"),
    ])

    monkeypatch.setattr(orchestrator, "get_next_step", lambda *args, **kwargs: next(steps))

    def _fake_execute_tool(ctx, tool_name, params, *, allowed_tools=None):
        captured["tool_name"] = tool_name
        captured["allowed_tools"] = allowed_tools
        captured["params"] = params
        return {"echo": params["text"]}

    monkeypatch.setattr(orchestrator, "execute_tool", _fake_execute_tool)

    result = orchestrator.handle_ai_request_with_thread(
        ctx=None,
        user_input="hello",
        prior_turns=[],
        capability_name="logistics",
        stage_name=EXECUTE_STAGE,
    )

    assert result.success is True
    assert result.final_message == "ok"
    assert captured["tool_name"] == "echo_tool"
    assert captured["params"] == {"text": "hello"}
    assert captured["allowed_tools"] is allowed_tools


def test_orchestrator_surfaces_presentation_hints_from_final_step(monkeypatch):
    capability = CapabilityProfile(
        name="logistics",
        description="logistics",
        prompt_builders={EXECUTE_STAGE: lambda **_kw: "stage-prompt"},
        tool_registries={EXECUTE_STAGE: {}},
    )

    monkeypatch.setattr(orchestrator, "get_capability_profile", lambda name: capability)
    monkeypatch.setattr(orchestrator, "select_provider_for_stage", lambda capability_name, stage_name: _DummyProvider())
    monkeypatch.setattr(
        orchestrator,
        "get_next_step",
        lambda *args, **kwargs: PlannerFinalStep(
            type="final",
            message="ok",
            presentation_hints={"blocks": [{"entity_type": "order", "columns": ["reference", "total_items"]}]},
        ),
    )

    result = orchestrator.handle_ai_request_with_thread(
        ctx=None,
        user_input="what orders contain items?",
        prior_turns=[],
        capability_name="logistics",
        stage_name=EXECUTE_STAGE,
    )

    assert result.success is True
    assert result.data["presentation_hints"]["blocks"][0]["columns"] == ["reference", "total_items"]


def test_user_config_capability_is_isolated_from_logistics_tools():
    capability = get_capability_profile("user_config")

    prompt = capability.build_prompt(EXECUTE_STAGE)
    tools = capability.get_tools(EXECUTE_STAGE)

    assert "user application configuration" in prompt.lower()
    assert "create_item_type_config" in tools
    assert "create_item_property_config" in tools
    assert "list_item_types_config" in tools
    assert "create_order" not in prompt


def test_statistics_capability_is_read_only_and_scoped():
    capability = get_capability_profile("statistics")

    prompt = capability.build_prompt(EXECUTE_STAGE)
    tools = capability.get_tools(EXECUTE_STAGE)

    assert "senior logistics data analyst" in prompt.lower()
    assert set(tools.keys()) == {
        "get_analytics_snapshot",
        "get_daily_summary",
        "get_route_metrics_tool",
    }
    assert "create_order" not in prompt


def test_execute_tool_injects_normalized_contact_facts_for_create_order():
    captured = {}

    def _fake_create_order(ctx, **params):
        captured["params"] = params
        return {"status": "created"}

    ctx = ServiceContext(
        incoming_data={
            "_ai_execution": {
                "normalized_facts": {
                    "client_email": "ana@example.com",
                    "client_primary_phone": {"prefix": "+46", "number": "701234567"},
                }
            }
        }
    )

    tool_executor.execute_tool(
        ctx,
        "create_order",
        {"client_first_name": "Ana"},
        allowed_tools={"create_order": _fake_create_order},
    )

    assert captured["params"]["client_email"] == "ana@example.com"
    assert captured["params"]["client_primary_phone"]["prefix"] == "+46"
    assert captured["params"]["client_primary_phone"]["number"] == "701234567"


def test_execute_tool_keeps_explicit_create_order_contact_values():
    captured = {}

    def _fake_create_order(ctx, **params):
        captured["params"] = params
        return {"status": "created"}

    ctx = ServiceContext(
        incoming_data={
            "_ai_execution": {
                "normalized_facts": {
                    "client_email": "ana@example.com",
                    "client_primary_phone": {"prefix": "+46", "number": "701234567"},
                }
            }
        }
    )

    tool_executor.execute_tool(
        ctx,
        "create_order",
        {
            "client_email": "override@example.com",
            "client_primary_phone": {"prefix": "+1", "number": "5551000"},
        },
        allowed_tools={"create_order": _fake_create_order},
    )

    assert captured["params"]["client_email"] == "override@example.com"
    assert captured["params"]["client_primary_phone"] == {"prefix": "+1", "number": "5551000"}


def test_execute_tool_clamps_broad_list_orders_limit_for_readable_blocks():
    captured = {}

    def _fake_list_orders(ctx, **params):
        captured["params"] = params
        return {"status": "ok"}

    ctx = ServiceContext(incoming_data={})

    tool_executor.execute_tool(
        ctx,
        "list_orders",
        {"limit": 1},
        allowed_tools={"list_orders": _fake_list_orders},
    )

    assert captured["params"]["limit"] == 50


def test_execute_tool_keeps_limit_for_targeted_list_orders_lookup():
    captured = {}

    def _fake_list_orders(ctx, **params):
        captured["params"] = params
        return {"status": "ok"}

    ctx = ServiceContext(incoming_data={})

    tool_executor.execute_tool(
        ctx,
        "list_orders",
        {"q": "1056", "s": ["order_scalar_id"], "limit": 1},
        allowed_tools={"list_orders": _fake_list_orders},
    )

    assert captured["params"]["limit"] == 1


def test_execute_tool_blocks_user_config_writes_outside_user_config_capability():
    ctx = ServiceContext(incoming_data={"_ai_route": {"capability_name": "logistics"}})

    try:
        tool_executor.execute_tool(
            ctx,
            "update_item_type_config",
            {"item_type_id": 1, "fields": {"name": "x"}},
            allowed_tools={"update_item_type_config": lambda ctx, **kwargs: {"status": "updated"}},
        )
    except ValueError as exc:
        assert "blocked outside user_config capability" in str(exc)
    else:
        raise AssertionError("Expected write guard to block non-user_config route")


def test_execute_tool_blocks_apply_without_confirmed_interaction():
    ctx = ServiceContext(
        incoming_data={
            "_ai_route": {"capability_name": "user_config"},
            "_ai_execution": {"confirm_accepted": False},
        }
    )

    try:
        tool_executor.execute_tool(
            ctx,
            "apply_item_taxonomy_proposal",
            {"proposal": {"item_types": []}, "approval_token": "tax_x", "approved": True},
            allowed_tools={"apply_item_taxonomy_proposal": lambda ctx, **kwargs: {"status": "applied"}},
        )
    except ValueError as exc:
        assert "confirm_accepted=true" in str(exc)
    else:
        raise AssertionError("Expected apply guard to require confirmed interaction")


def test_orchestrator_includes_error_code_when_tool_fails(monkeypatch):
    allowed_tools = {"failing_tool": lambda ctx, **kwargs: {}}
    capability = CapabilityProfile(
        name="logistics",
        description="logistics",
        prompt_builders={EXECUTE_STAGE: lambda **_kw: "stage-prompt"},
        tool_registries={EXECUTE_STAGE: allowed_tools},
    )

    monkeypatch.setattr(orchestrator, "get_capability_profile", lambda name: capability)
    monkeypatch.setattr(orchestrator, "select_provider_for_stage", lambda capability_name, stage_name: _DummyProvider())

    steps = iter([
        PlannerToolStep(type="tool", tool="failing_tool", parameters={}),
        PlannerFinalStep(type="final", message="done"),
    ])
    monkeypatch.setattr(orchestrator, "get_next_step", lambda *args, **kwargs: next(steps))

    class _ProposalExpired(Exception):
        code = "proposal_expired"

    def _fake_execute_tool(ctx, tool_name, params, *, allowed_tools=None):
        raise _ProposalExpired("This proposal has expired and can no longer be applied.")

    monkeypatch.setattr(orchestrator, "execute_tool", _fake_execute_tool)

    result = orchestrator.handle_ai_request_with_thread(
        ctx=None,
        user_input="apply proposal",
        prior_turns=[],
        capability_name="logistics",
        stage_name=EXECUTE_STAGE,
    )

    assert result.success is True
    assert len(result.tool_turns) == 1
    assert result.tool_turns[0]["result"]["error_code"] == "proposal_expired"