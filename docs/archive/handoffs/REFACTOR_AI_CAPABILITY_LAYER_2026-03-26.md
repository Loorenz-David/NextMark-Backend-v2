# Refactor: AI Capability Layer
**Date:** 2026-03-26  
**Status:** PAUSED — unit tests green (134/134), integration tests and service/label correctness pending  
**Branch context:** Paused to stabilize `/services` route operations and labeling before resuming

---

## Why This Refactor Exists

The AI module had a flat, single-stage orchestrator. As capabilities grew (logistics, statistics, user_config, analytics), the module needed:

- A **stage-aware** orchestrator (INTENT → CLARIFY → EXECUTE) so each capability can govern its own prompt, tools, and clarification flow
- **Typed planner step contracts** instead of raw dict parsing
- A **block-first response formatter** that maps every tool result to a typed `AIBlock`, with proper table column hints, AI focus, and analytics risk briefs
- **Router-level capability policy** helpers to route mixed-intent messages to the right capability
- A **schema layer** rich enough to carry interactions, warnings, rendering hints, and presentation hints through the full response pipeline

---

## Files Modified

| File | Change Type | Summary |
|---|---|---|
| `Delivery_app_BK/ai/schemas.py` | Major expansion | Added `AIBlock`, `AIWarning`, `AIInteraction`, `AIField`, `AIOption`, `PlannerIntentStep`, `PlannerClarifyStep`, `PlannerToolStep`, `PlannerFinalStep`, `PresentationHints`, `PresentationHintBlock`, `parse_planner_step()`. Updated `AIThreadMessagePayload` and `AIThreadTurn` with blocks, interactions, typed_warnings, rendering_hints, awaiting_response, interaction_kind/id, interaction_form. Changed `AIInteraction.options` and `.fields` to `List[Dict[str, Any]]` so they stay subscriptable for test/client consumers. |
| `Delivery_app_BK/ai/planner.py` | Updated | Returns typed `PlannerStepContract` objects via `parse_planner_step()`. Deduplicates user message when history tail already matches current input. |
| `Delivery_app_BK/ai/tool_executor.py` | Extended | Added `_OPERATION_TO_TOOL_ALLOWLIST`, `_USER_CONFIG_WRITE_TOOLS`, `_validate_capability_guard()`, `_validate_operation_allowlist()`. Expanded `_apply_execution_facts` with `list_orders` limit clamping (≥50 unless targeted lookup). Handles `None` ctx safely. |
| `Delivery_app_BK/ai/orchestrator.py` | Full rebuild | See detail below. |
| `Delivery_app_BK/ai/response_formatter.py` | Full rebuild | See detail below. |
| `Delivery_app_BK/routers/api_v2/ai.py` | Extended | Added capability/policy helper functions without changing HTTP handlers. See detail below. |
| `Delivery_app_BK/routers/api_v2/__init__.py` | Lazy-loading | Rewrote to lazy-load all blueprint imports via `__getattr__`. Prevents cascade import failures when any one blueprint module has a broken import at collection time. |
| `Delivery_app_BK/models/tables/delivery_plan/delivery_plan.py` | Alias added | Added `DeliveryPlan` alias for backwards-compat imports. |
| Multiple delivery plan query modules | Import fixes | Fixed broken relative import depths across 6+ files (context, utils, get_instance). See section below. |

---

## Orchestrator (`orchestrator.py`) — Full Rebuild Detail

### Public API
```python
def handle_ai_request_with_thread(
    ctx: ServiceContext | None,
    user_input: str,
    prior_turns: list[AIThreadTurn],
    provider: Any | None = None,
    system_prompt: str | None = None,
    capability_name: str | None = None,
    stage_name: str = EXECUTE_STAGE,
    interaction_response_payload: dict[str, Any] | None = None,
) -> OrchestratorResult:
```

### `OrchestratorResult` dataclass
```python
@dataclass
class OrchestratorResult:
    final_message: str
    tool_turns: list[dict] = field(default_factory=list)
    success: bool = True
    data: dict | None = None
    interactions: list[AIInteraction] = field(default_factory=list)
    reuse_recent_tool_turns: bool = False
```

### Stage flow (when `capability_name` is set and `stage_name=EXECUTE_STAGE`)
1. **Check if capability has INTENT_STAGE prompt** — if not, skip intent/clarify and go directly to execute loop
2. **INTENT stage** — calls `get_next_step` with intent prompt → returns `PlannerIntentStep(operation, needs_clarification)`
3. **CLARIFY stage** (only if `needs_clarification=True`) — calls `get_next_step` with clarify prompt → returns early with clarify interaction
4. **EXECUTE loop** — runs up to `MAX_STEPS=5` iterations; handles `PlannerToolStep`, `PlannerClarifyStep`, `PlannerFinalStep`
5. **Statistics validation** — for `capability_name="statistics"` + `operation="analyze_metrics"`, validates JSON payload; attempts one repair pass; returns structured error with `statistical_output_validation` key if both fail
6. **Retrieval repair** — if final step fires with no tool calls and the user intent implies a retrieval operation, injects a corrective message and retries once
7. **Analytics chaining** — for logistics + retrieval operations with `insight_depth` set, automatically appends a `get_analytics_snapshot` turn

### Key helpers added
- `_normalize_phone(raw_phone)` → `{client_primary_phone: {prefix, number}, client_phone_raw}`
- `_normalize_timeframe(value)` → canonical form (`"24h"`, `"7d"`, `"30d"`)
- `_merge_execution_facts(ctx, interaction_response_payload)` — writes normalized facts into `ctx.incoming_data["_ai_execution"]`
- `_turns_to_planner_history(turns)` — replays `AIThreadTurn` list (including interaction form turns) into LLM history format
- `_build_interaction_response_history(turn)` — serializes interaction form turns with normalized facts (uses insertion-order JSON, no `sort_keys`)
- `_append_logistics_analytics_snapshot(ctx, result, *, user_input, allowed_tools, timeframe, insight_depth)` — infers timeframe from `user_input` when caller doesn't pass an explicit `timeframe`
- `_should_chain_logistics_analytics(...)`, `_infer_analytics_timeframe(user_input)`
- `_parse_statistics_payload(raw_message)` → `(is_valid, kind, payload_or_errors)` — validates narrative/legacy/partial payloads, always reports `confidence_score` missing
- `_statistics_validation_errors(payload, kind)` → list of `{loc, msg}` error dicts

### Cancellation flow
When `interaction_response_payload.confirm_accepted is False` and a matching `awaiting_response` turn is found in history, returns immediately with `interaction_cancelled=True` data.

---

## Response Formatter (`response_formatter.py`) — Full Rebuild Detail

### Public API
```python
def format_response(
    thread_id: str,
    final_message: str,
    tool_turns: list[dict],
    *,
    success: bool = True,
    data: dict | None = None,
    interactions_override: list[AIInteraction] | None = None,
    narrative_policy_override: str | None = None,
    presentation_hints_override: dict | None = None,
    user_query_override: str | None = None,
    operation_name: str | None = None,
) -> AIThreadMessageResponse:
```

### Block generation (`generate_blocks`)
Maps every tool type to a typed `AIBlock`:

| Tool | Block kind | Layout | Notes |
|---|---|---|---|
| `geocode_address` | `entity_detail` | `key_value` | raw result |
| `create_order` | `entity_detail` | `key_value` | unwraps nested created order |
| `list_orders` | `entity_collection` | `table` | normalizes items, attaches ai_focus for late/unassigned, uses `meta.table.columns` |
| `list_plans` | `entity_collection` | `table` | normalizes plan items |
| `list_routes` | `entity_collection` | `table` | normalizes route items |
| `create_plan` | `entity_detail` | `key_value` | |
| `assign_orders_to_plan` | `summary` | `summary` | |
| `update_order_state` | `summary` | `summary` | |
| `optimize_plan` | `summary` | `summary` | injects plan_id from params |
| `update_order` | `entity_detail` | `key_value` | |
| `add_items_to_order` | `entity_detail` | `key_value` | |
| `search_item_types` | `entity_collection` | `chips` | adds article suffix reference |
| `list_item_types_config` | `entity_collection` | `table` | |
| `list_item_properties_config` | `entity_collection` | `table` | |
| `get_analytics_snapshot` | `analytics_kpi` + `analytics_trend` + `analytics_breakdown` | mixed | |
| any other | `summary` | `summary` | passthrough |

**Important guard:** `format_response` only overwrites `blocks[0].meta["table"]["columns"]` when `blocks[0].entity_type == "order"` **and** `blocks[0].meta.get("table")` exists (i.e. not a `key_value` block from `create_order`).

### Other formatter functions
- `format_tool_trace(tool_turns)` → `list[AIToolTraceEntry]` with per-tool summarization
- `generate_actions(tool_turns)` → `list[AIAction]` (navigate/filter actions)
- `generate_interactions(tool_turns)` → `list[AIInteraction]` — auto-generates select/confirm interactions for ambiguous plan_types, multiple drivers, bulk order state updates, large assign operations
- `validate_ai_focus_warnings(blocks)` → `list[AIWarning]` — reports `AI_FOCUS_MISMATCH` when focused entity IDs are absent from block items
- `_build_risk_brief_block(tool_turns, insight_depth)` → optional `AIBlock` with risk level from analytics metrics

---

## Router Policy Helpers (`routers/api_v2/ai.py`)

Added without touching HTTP handler signatures:

```python
_KNOWN_CAPABILITY_IDS = {"analytics", "statistics", "logistics", "user_config"}

_TOOL_TO_CAPABILITY: dict[str, str]         # 28 tools mapped to their capability
_OPERATION_TO_TOOL_ALLOWLIST: dict[str, set] # 8 operations mapped to allowed tools

_message_capability_hint(message)           # Quick keyword heuristic → capability id or None
_has_mixed_capability_intent(message)       # True if message spans multiple capabilities
_resolve_capability_auto(message)           # Single-capability fast-path resolver
_build_mixed_intent_interaction(message)    # Returns AIInteraction(kind="question") for mixed-intent
_parse_capability_router_output(raw)        # Parses LLM-produced capability JSON
_resolve_capability_plan_auto_with_llm(ctx, message, provider) # Full LLM-based resolution
_parse_requested_capability_policy(...)     # Validates requested capability against allowlist
_resolve_tool_policy(...)                   # Assembles per-request tool policy
_merge_policy_metadata(...)                 # Merges policy metadata into response data
_apply_tool_policy_to_response(...)         # Applies policy to OrchestratorResult
```

---

## Delivery Plan Import Fixes

Several query modules under `Delivery_app_BK/services/queries/delivery_plan/` had broken relative import depths (e.g. `from ...context` when the correct depth was `from Delivery_app_BK.services.context`). Fixed:

- `plan_states/find_plan_states.py`
- `plan_states/get_plan_state.py`
- `plan_states/list_plan_states.py`
- `plan_states/serialize_plan_states.py`
- `plan_types/serialize_local_delivery_plan.py`
- `plan_types/get_local_delivery_plan.py`

---

## Test Status at Pause Point

### Unit tests (all green ✅)
```
134 passed in 1.09s
```

Covers: `test_planner_step_contracts`, `test_planner_dedup_current_user`, `test_stage_foundation`, `test_orchestrator_interactions`, `test_ai_router_operation_allowlist`, `test_response_formatter`, `test_statistics_regression_matrix`

### Integration tests (blocked ❌)
```
ERROR tests/integration/ai/test_ai_thread_geocode_flow.py
ImportError: cannot import name 'AIInteractionField' from 'Delivery_app_BK.ai.schemas'
```

**Root cause:** `test_ai_thread_geocode_flow.py` imports `AIInteractionField` from `schemas.py`, but the schema class is named `AIField`. Either:
- **Option A:** Add `AIInteractionField = AIField` alias in `schemas.py` (one line)
- **Option B:** Update the integration test import to use `AIField`

**Recommendation:** Option A (add alias) — non-breaking, one line.

---

## Remaining Work When Resuming

### Immediate (unblock integration test suite)
- [ ] Add `AIInteractionField = AIField` alias in `Delivery_app_BK/ai/schemas.py`
- [ ] Run integration tests and fix any behavioral regressions in `test_ai_thread_geocode_flow.py` and `test_capability_policy_contract.py`

### Service-level work (depends on services stabilization)
- [ ] Audit `routers/api_v2/ai.py` HTTP handlers against the finalized service/request layer — some handler calls may have stale parameter shapes after service labeling refactor
- [ ] Validate `tool_executor.py` tool dispatch against final service call signatures in `/services/requests/`
- [ ] Confirm `_apply_execution_facts` in `tool_executor.py` correctly maps normalized facts (phone, timeframe, confirm_accepted) to the real service request DTOs once those are re-labeled
- [ ] `thread_store` persistence of `AIThreadTurn` — confirm new fields (`blocks`, `interactions`, `interaction_form`, `awaiting_response`) are being stored and retrieved correctly in the database-backed turn store (currently tested only with in-memory stubs)

### Polish / future capability work
- [ ] `PlannerIntentStep` — add `reason` field surface-through to response `data` for client debug tooling
- [ ] Expand `_OPERATION_TO_TOOL_ALLOWLIST` in `tool_executor.py` as new operations are added to capabilities
- [ ] `_append_logistics_analytics_snapshot` — currently always calls `get_analytics_snapshot`; consider caching within a thread session to avoid redundant LLM/tool calls
- [ ] Response formatter `_extract_order_columns` — driven by `presentation_hints` from `PlannerFinalStep`. Needs end-to-end test with a real LLM provider output to validate column hints round-trip

---

## How to Resume

```bash
# Run unit tests first to confirm baseline is still green
PYTHONPATH="$PWD" .venv/bin/python -m pytest tests/unit/ai/ -q

# Unblock integration tests
# Add to Delivery_app_BK/ai/schemas.py (after AIField definition):
AIInteractionField = AIField

# Then run integration tests
PYTHONPATH="$PWD" .venv/bin/python -m pytest tests/integration/ai/ -v

# Full suite
PYTHONPATH="$PWD" .venv/bin/python -m pytest -q
```
