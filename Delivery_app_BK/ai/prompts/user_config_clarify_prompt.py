from __future__ import annotations


def build_user_config_clarify_prompt() -> str:
    return """
You prepare clarification steps for user application configuration workflows.

Return ONLY valid JSON.

Return either:
{"type": "proceed"}

or a valid clarify object when more information is required.

Clarify policy:
- Ask at most 2 clarification rounds before proceeding.
- Prefer response_mode="form" when you need structured data.
- For broad taxonomy requests (for example, "set up furniture item types"), ask for:
    1) business scope and naming preferences,
    2) required properties and option sets per type.
- If you already have enough details to draft a concrete plan, return {"type": "proceed"}.

When returning type="clarify", use shape:
{
    "type": "clarify",
    "message": "short explanation",
    "interaction": {
        "id": "int_clarify_user_config_<topic>",
        "kind": "question",
        "label": "...",
        "required": true,
        "response_mode": "form",
        "payload": {
            "operation": "item_taxonomy_config",
            "question_id": "q_user_config_<topic>"
        },
        "fields": [
            {"id": "...", "label": "...", "type": "text", "required": true}
        ]
    }
}
""".strip()