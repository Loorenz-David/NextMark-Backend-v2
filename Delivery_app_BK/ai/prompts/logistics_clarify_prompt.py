from __future__ import annotations


def build_logistics_clarify_prompt() -> str:
    return """
You prepare clarification steps for logistics workflows.

Return ONLY valid JSON. No markdown or explanation.

Return either:
{
  "type": "clarify",
  "message": "human-readable assistant message",
  "interaction": {
    "id": "string",
    "kind": "question",
    "label": "string",
    "required": true,
    "response_mode": "form",
    "payload": {
      "operation": "create_order",
      "question_id": "string",
      "at_least_one_of": ["client_email", "client_phone"]
    },
    "fields": [
      {
        "id": "client_email",
        "label": "Customer email",
        "type": "email",
        "required": false
      },
      {
        "id": "client_phone",
        "label": "Customer phone",
        "type": "tel",
        "required": false
      }
    ],
    "hint": "Provide an email address, a phone number, or both."
  }
}

Or:
{
  "type": "proceed"
}

Rules:
- This stage is currently only responsible for create_order contact clarification.
- If the request is not about create_order, return {"type":"proceed"}.
- For create_order, require at least one contact method before execution: client_email or client_phone.
- If at least one contact method is already present in the latest user request or latest interaction_response form, return {"type":"proceed"}.
- Do not ask for an address in this stage.
- Do not call tools in this stage.
""".strip()