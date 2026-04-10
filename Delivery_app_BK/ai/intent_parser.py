from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from Delivery_app_BK.ai.capabilities.registry import CAPABILITY_REGISTRY
from Delivery_app_BK.ai.prompts_v2.capability_router_prompt import build_capability_router_prompt
from Delivery_app_BK.ai.providers.base import LLMProvider
from Delivery_app_BK.ai.providers.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IntentParseResult:
    capability_name: str
    needs_clarification: bool = False
    clarification_question: str = ""
    reason: str = ""


def parse_capability_intent(
    user_input: str,
    *,
    default_capability: str = "logistics",
    provider: LLMProvider | None = None,
) -> IntentParseResult:
    capabilities = list(CAPABILITY_REGISTRY.keys())
    if default_capability not in CAPABILITY_REGISTRY:
        default_capability = "logistics"

    try:
        provider = provider or OpenAIProvider()
        system_prompt = build_capability_router_prompt(capabilities)
        raw = provider.complete(system=system_prompt, user=user_input)
    except Exception as exc:
        logger.warning("Capability intent parser failed; defaulting | error=%s", exc)
        return IntentParseResult(capability_name=default_capability, reason="intent_parser_error")

    payload = _coerce_json_object(raw)
    selected = _select_capability(payload, default_capability)

    return IntentParseResult(
        capability_name=selected,
        needs_clarification=bool(payload.get("needs_clarification", False)),
        clarification_question=str(payload.get("clarification_question") or ""),
        reason=str(payload.get("reason") or ""),
    )


def _select_capability(payload: dict, default_capability: str) -> str:
    ordered = payload.get("ordered_capability_ids") or []
    ids = payload.get("capability_ids") or []

    for candidate in [*ordered, *ids]:
        if isinstance(candidate, str) and candidate in CAPABILITY_REGISTRY:
            return candidate

    return default_capability


def _coerce_json_object(content: str) -> dict:
    raw = (content or "").strip()
    if not raw:
        return {}

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL)
    if fenced:
        try:
            parsed = json.loads(fenced.group(1))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    inline = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if inline:
        try:
            parsed = json.loads(inline.group(0))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    return {}
