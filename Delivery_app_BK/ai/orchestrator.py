from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field

from Delivery_app_BK.services.context import ServiceContext

from .planner import get_next_step
from .tool_executor import execute_tool
from .providers.base import LLMProvider
from .providers.openai_provider import OpenAIProvider
from .schemas import AIThreadTurn

logger = logging.getLogger(__name__)

MAX_STEPS = 5


@dataclass
class OrchestratorResult:
    final_message: str
    tool_turns: list[dict] = field(default_factory=list)
    success: bool = True
    data: dict | None = None


def handle_ai_request_with_thread(
    ctx: ServiceContext,
    user_input: str,
    prior_turns: list[AIThreadTurn],
    provider: LLMProvider | None = None,
    system_prompt: str | None = None,
) -> OrchestratorResult:
    """
    Run the planner loop, seeding it with prior thread turns as history.
    Returns a structured OrchestratorResult instead of an AIResponse.
    """
    provider = provider or OpenAIProvider()

    # Convert stored thread turns into the planner's {tool, params, result} history format
    history: list[dict] = _turns_to_planner_history(prior_turns)
    tool_turns_this_request: list[dict] = []

    logger.info(
        "AI thread request | provider=%s | input=%r | prior_turns=%d",
        provider.name,
        user_input,
        len(prior_turns),
    )

    try:
        for step_num in range(MAX_STEPS):
            step = get_next_step(user_input, history, provider, system_prompt=system_prompt)

            if step.get("type") == "final":
                message = step.get("message", "Done.")
                logger.info(
                    "AI thread request complete | steps=%d | message=%r",
                    step_num + 1,
                    message,
                )
                return OrchestratorResult(
                    final_message=message,
                    tool_turns=tool_turns_this_request,
                    success=True,
                )

            if step.get("type") == "tool":
                tool_name = step.get("tool", "")
                params = step.get("parameters") or {}

                try:
                    result = execute_tool(ctx, tool_name, params)
                except Exception as e:
                    logger.warning("Tool execution failed | tool=%s | error=%s", tool_name, e)
                    result = {"error": str(e)}

                entry = {"tool": tool_name, "params": params, "result": result}
                history.append(entry)
                tool_turns_this_request.append(entry)
                continue

            logger.warning("Unknown step type from planner: %s", step)
            break

        logger.warning("AI request hit MAX_STEPS=%d", MAX_STEPS)
        return OrchestratorResult(
            final_message="Max steps reached without completing the request.",
            tool_turns=tool_turns_this_request,
            success=False,
        )

    except Exception as e:
        logger.exception("Unexpected error in AI request | input=%r", user_input)
        return OrchestratorResult(
            final_message=str(e),
            tool_turns=tool_turns_this_request,
            success=False,
        )


def _turns_to_planner_history(turns: list[AIThreadTurn]) -> list[dict]:
    """
    Convert stored thread turns → planner message history.

    We replay all roles so the LLM has full conversational context across
    requests — user questions, tool calls, tool results, and prior answers.
    Without user + assistant turns, pronouns like "those orders" or "them"
    have no antecedent and the LLM loses cross-turn context.

    Planner message format:
      user turn      → {"role": "user",      "content": <question>}
      tool turn      → {"role": "assistant",  "content": JSON tool call}
                       {"role": "user",       "content": "Tool result for X: ..."}
      assistant turn → {"role": "assistant",  "content": JSON final answer}
    """
    history: list[dict] = []
    for turn in turns:
        if turn.role == "user":
            history.append({"role": "user", "content": turn.content})

        elif turn.role == "tool" and turn.tool_name:
            history.append({
                "role": "assistant",
                "content": json.dumps({
                    "type": "tool",
                    "tool": turn.tool_name,
                    "parameters": turn.tool_params or {},
                }),
            })
            history.append({
                "role": "user",
                "content": f"Tool result for {turn.tool_name}: {json.dumps(turn.tool_result or {})}",
            })

        elif turn.role == "assistant":
            history.append({
                "role": "assistant",
                "content": json.dumps({
                    "type": "final",
                    "message": turn.content,
                }),
            })

    return history


# ---------------------------------------------------------------------------
# V1 entry point — removed. All callers should use handle_ai_request_with_thread.
# ---------------------------------------------------------------------------

