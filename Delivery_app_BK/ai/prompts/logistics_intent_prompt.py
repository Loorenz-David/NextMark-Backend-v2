from __future__ import annotations


def build_logistics_intent_prompt() -> str:
    return """
You classify logistics requests.

Return ONLY valid JSON. No markdown or explanation.

Return shape:
{
  "type": "intent",
  "operation": "<operation>",
  "insight_depth": "none" | "risk_brief" | "diagnostic",
  "needs_clarification": true | false,
  "reason": "short explanation"
}

Allowed operation values (pick the BEST match):
  "list_orders"        - user wants to see, find, count, or search orders
  "list_plans"         - user wants to see, find, count, or search delivery plans
  "create_order"       - user wants to create, place, register, or add a new order
  "create_plan"        - user wants to create a new delivery plan
  "assign_orders"      - user wants to schedule or assign orders to a plan
  "optimize_plan"      - user wants to run route optimization on a plan
  "update_order_state" - user wants to change the state of one or more orders
  "update_order"       - user wants to edit fields on an existing order
  "other"              - a valid logistics request that does not match the above
  "unknown"            - cannot classify the request confidently

Rules:
- Focus on the latest user request and any latest interaction_response already present in history.
- Use the most specific operation that fits. Prefer specific labels over "other" or "unknown".
- For retrieval operations (list_orders, list_plans), default insight_depth to "risk_brief"
  unless the user clearly asks for only raw data.
- Use insight_depth="diagnostic" when the user asks why, root cause, risk analysis,
  or optimization reasoning.
- Use insight_depth="none" for pure operational actions/mutations (create/update/assign/optimize).
- Set needs_clarification=true ONLY when operation="create_order" and the user has not provided
  at least one customer contact method (email address or phone number).
- Do not call tools in this stage.
""".strip()