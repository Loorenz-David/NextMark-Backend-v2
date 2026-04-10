from __future__ import annotations
import json
import logging

from .providers.base import LLMProvider
from .prompts.system_prompt import PLANNER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def get_next_step(
    user_input: str,
    history: list[dict],
    provider: LLMProvider,
    system_prompt: str | None = None,
) -> dict:
    """
    Build a conversation and get the next planner step from the LLM.

    history entries are one of two shapes:
      - cross-request turns (from _turns_to_planner_history):
          {"role": "user"|"assistant", "content": "..."}
      - within-request tool steps (appended during the loop):
          {"tool": "...", "params": {...}, "result": {...}}

    The current user_input is always appended last so the LLM sees the full
    prior conversation before receiving the new question.

    system_prompt: optional override; falls back to PLANNER_SYSTEM_PROMPT.
    """
    active_prompt = system_prompt or PLANNER_SYSTEM_PROMPT
    messages: list[dict] = [
        {"role": "system", "content": active_prompt},
    ]

    # Replay history — two formats supported
    for entry in history:
        if "role" in entry:
            # Already a formatted message (cross-request turn)
            messages.append(entry)
        else:
            # Within-request tool step: {tool, params, result}
            messages.append({
                "role": "assistant",
                "content": json.dumps({
                    "type": "tool",
                    "tool": entry["tool"],
                    "parameters": entry.get("params", {}),
                }),
            })
            messages.append({
                "role": "user",
                "content": f"Tool result for {entry['tool']}: {json.dumps(entry['result'])}",
            })

    # Current user message goes last — after all prior context
    messages.append({"role": "user", "content": user_input})

    try:
        content = _complete_with_history(provider, messages)
        return json.loads(content)
    except Exception:
        logger.warning("Failed to parse planner step from LLM response")
        return {"type": "final", "message": "Failed to process the request. Please try again."}


def _complete_with_history(provider: LLMProvider, messages: list[dict]) -> str:
    """
    Multi-turn completion using full message history.
    Uses provider's underlying client if it's OpenAIProvider,
    otherwise falls back to single-turn complete() with serialized history.
    """
    # Try to use the OpenAI client directly for proper multi-turn conversation
    try:
        from .providers.openai_provider import OpenAIProvider
        if isinstance(provider, OpenAIProvider):
            response = provider._client.chat.completions.create(
                model=provider._model,
                messages=messages,
                temperature=0,
            )
            return response.choices[0].message.content or ""
    except Exception:
        pass

    # Fallback: serialize history into user message for other providers
    last_user = messages[-1]["content"] if messages else ""
    return provider.complete(
        system=messages[0]["content"],
        user=last_user,
    )
