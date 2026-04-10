from __future__ import annotations


def build_user_config_intent_prompt() -> str:
    return """
You classify user application configuration requests.

Return ONLY valid JSON.

Return shape:
{
  "type": "intent",
  "operation": "item_taxonomy_config" | "user_config" | "unknown",
  "needs_clarification": true | false,
  "reason": "short explanation"
}

Guidance:
- Use operation="item_taxonomy_config" for requests about item types, item properties, required fields, options, or category structure.
- Set needs_clarification=true when the request is broad/vague or does not specify enough constraints to safely apply writes.
""".strip()