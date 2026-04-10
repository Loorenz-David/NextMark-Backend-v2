from __future__ import annotations


def build_statistics_intent_prompt() -> str:
    return """
You classify statistical analytics requests for logistics performance.

Return ONLY valid JSON. No markdown or explanation.

Return shape:
{
  "type": "intent",
  "operation": "analyze_metrics" | "other" | "unknown",
  "needs_clarification": true | false,
  "reason": "short explanation"
}

Rules:
- Use operation="analyze_metrics" for analytical questions about performance, trends, anomalies, delays, comparisons, or what changed over time.
- Examples: "why are deliveries late", "show performance", "what happened this week", "analytics for last 30 days".
- Do not classify operational troubleshooting questions (for example order mutation failures) as analyze_metrics unless they explicitly request analytics/trend interpretation.
- Set needs_clarification=true only when timeframe is missing or ambiguous.
- Do not call tools in this stage.
""".strip()
