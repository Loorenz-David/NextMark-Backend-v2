from __future__ import annotations


def build_statistics_clarify_prompt() -> str:
    return """
You prepare clarification steps for analytics workflows.

Return ONLY valid JSON. No markdown or explanation.

Return either:
{"type": "proceed"}

or:
{
  "type": "clarify",
  "message": "human-readable assistant message",
  "interaction": {
    "id": "int_clarify_statistics_timeframe",
    "kind": "question",
    "label": "Choose a timeframe",
    "required": true,
    "response_mode": "select",
    "payload": {
      "operation": "analyze_metrics",
      "question_id": "q_statistics_timeframe",
      "fallback_timeframe": "last_7_days"
    },
    "options": [
      {"id": "24h", "label": "Last 24 hours"},
      {"id": "7d", "label": "Last 7 days"},
      {"id": "30d", "label": "Last 30 days"}
    ],
    "hint": "If no timeframe is provided, use last_7_days."
  }
}

Rules:
- This stage handles only analyze_metrics timeframe clarification.
- If a clear timeframe is already present in the latest user request or interaction response, return {"type":"proceed"}.
- Default fallback timeframe is last_7_days.
- Do not call tools in this stage.
""".strip()
