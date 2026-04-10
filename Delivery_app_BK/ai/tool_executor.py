from __future__ import annotations
import logging
from collections.abc import Mapping
from typing import Any

from Delivery_app_BK.services.context import ServiceContext
from .tool_registry import TOOLS

logger = logging.getLogger(__name__)


def _apply_execution_facts(tool_name: str, params: dict, ctx: ServiceContext) -> dict:
    if tool_name != "create_order":
        return params

    execution_payload = (ctx.incoming_data or {}).get("_ai_execution") or {}
    normalized_facts = execution_payload.get("normalized_facts") or {}
    if not isinstance(normalized_facts, dict):
        return params

    enriched = dict(params)

    # Prefer explicit planner-provided values. Fill only missing fields.
    if "client_email" not in enriched and normalized_facts.get("client_email"):
        enriched["client_email"] = normalized_facts["client_email"]

    if "client_primary_phone" not in enriched and normalized_facts.get("client_primary_phone"):
        enriched["client_primary_phone"] = normalized_facts["client_primary_phone"]

    return enriched


def execute_tool(
    ctx: ServiceContext,
    tool_name: str,
    params: dict,
    *,
    allowed_tools: Mapping[str, Any] | None = None,
) -> dict:
    registry = allowed_tools or TOOLS
    if tool_name not in registry:
        raise ValueError(f"Tool '{tool_name}' is not registered. Allowed: {list(registry.keys())}")

    tool_fn = registry[tool_name]
    effective_params = _apply_execution_facts(tool_name, params, ctx)
    logger.info("Executing tool | tool=%s | params=%s", tool_name, params)

    result = tool_fn(ctx, **effective_params)

    # Ensure result is always a dict
    if not isinstance(result, dict):
        result = {"result": result}

    return result
