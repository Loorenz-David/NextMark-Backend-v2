# AI Clarification Form Contract

> Status: Backend contract implemented, generation still pending
> Last updated: March 21, 2026
> Audience: Frontend Copilot / frontend engineers adapting the AI panel UI



## Purpose

This document defines the contract for a new interaction pattern: a single blocking clarification form that collects multiple missing fields in one assistant turn.

This is the preferred pattern when the AI cannot continue because several independent inputs are missing at the same time.

Example:

- User says: "Create order for Ana"
- Backend knows required information is missing:
  - delivery address
  - phone number
- Instead of asking two separate blocking questions across two turns, the assistant sends one structured clarification form.

This reduces round trips, improves task completion speed, and gives the frontend a much better UX than sequential modal prompts.

---

## When To Use This Pattern

Use a clarification form when all of the following are true:

1. The workflow is blocked because required data is missing.
2. More than one missing field can be collected independently.
3. The questions do not depend on each other.

Use sequential single questions instead when later questions depend on earlier answers.

Examples:

- Good fit for clarification form:
  - create order missing address and phone
  - create plan missing label and date range
  - update order missing both contact name and phone

- Not a good fit for clarification form:
  - first choose delivery type, then ask different follow-up questions based on that type
  - first confirm a dangerous action, then ask for options only if confirmed

---

## High-Level Model

This does not introduce a new top-level interaction kind.

Instead, it extends the existing question interaction family:

- kind = question
- required = true
- response_mode = form
- fields = array of structured field definitions

This keeps the interaction model consistent:

- continue_prompt = optional conversational shortcut
- question + select = choose one answer
- question + text = free-text answer
- question + form = multi-field clarification
- confirm = risky-operation approval

---

## Response Contract

### Interaction Shape

```json
{
  "id": "int_clarify_create_order",
  "kind": "question",
  "label": "I need a few more details to create this order",
  "required": true,
  "response_mode": "form",
  "hint": "You can leave optional fields empty if the customer did not provide them.",
  "payload": {
    "question_id": "q_create_order_missing_fields",
    "source_tool": "create_order",
    "intent": "create_order",
    "entity_type": "order"
  },
  "fields": [
    {
      "id": "client_address",
      "label": "Delivery address",
      "type": "text",
      "required": false,
      "placeholder": "Street, city, postal code",
      "help_text": "Enter a full address, or choose 'No address'.",
      "suggestions": [
        { "id": "no_address", "label": "No address" }
      ]
    },
    {
      "id": "client_phone",
      "label": "Phone number",
      "type": "text",
      "required": true,
      "placeholder": "+46 70 123 45 67",
      "validation": {
        "pattern": "phone"
      }
    }
  ]
}
```

---

## Extended Schema

The current interaction model already supports:

- id
- kind
- label
- payload
- required
- response_mode
- options
- hint
- disabled

For clarification forms, the contract adds one new property:

- fields

### Proposed Field Schema

```ts
type AIInteractionField = {
  id: string;
  label: string;
  type: "text" | "textarea" | "phone" | "email" | "number" | "date" | "datetime" | "select" | "boolean";
  required?: boolean;
  placeholder?: string;
  help_text?: string;
  default_value?: string | number | boolean | null;
  options?: Array<{ id: string; label: string }>;
  suggestions?: Array<{ id: string; label: string }>;
  validation?: {
    pattern?: "phone" | "email" | "postal_code";
    min?: number;
    max?: number;
    max_length?: number;
  };
};
```

### Interaction Shape With Fields

```ts
type AIInteraction = {
  id?: string;
  kind: "ui_action" | "continue_prompt" | "question" | "confirm";
  label: string;
  payload?: Record<string, unknown>;
  required?: boolean;
  response_mode?: "text" | "select" | "confirm" | "form";
  options?: Array<{ id: string; label: string }>;
  fields?: AIInteractionField[];
  hint?: string;
  disabled?: boolean;
};
```

Notes:

- `fields` is only meaningful when `kind = question` and `response_mode = form`
- `options` continues to be used for select-based questions
- frontend should ignore `fields` for non-form interactions

---

## Request Contract Back To Backend

When the user submits the form, frontend sends the response through the same thread endpoint.

### Request Shape

```json
{
  "message": "Clarification form submitted",
  "__interaction_response__": "int_clarify_create_order",
  "interaction_form": {
    "client_address": "Kungsgatan 5, Stockholm",
    "client_phone": "+46 70 123 45 67"
  }
}
```

### Important Rules

1. `__interaction_response__` must match the active blocking interaction id.
2. `interaction_form` contains the actual field values.
3. `message` can be a generic assistant-safe string such as:
   - `"Clarification form submitted"`
   - `"Provided missing order details"`
4. Backend should use `interaction_form` as the source of truth, not the free-text `message`.

---

## Example: Create Order Missing Address And Phone

### Assistant Response

```json
{
  "data": {
    "thread_id": "thr_abc123",
    "message": {
      "role": "assistant",
      "content": "I can create this order, but I still need a few details.",
      "interactions": [
        {
          "id": "int_clarify_create_order",
          "kind": "question",
          "label": "I need a few more details to create this order",
          "required": true,
          "response_mode": "form",
          "payload": {
            "question_id": "q_create_order_missing_fields",
            "intent": "create_order",
            "entity_type": "order"
          },
          "fields": [
            {
              "id": "client_address",
              "label": "Delivery address",
              "type": "text",
              "required": false,
              "placeholder": "Street, city, postal code",
              "suggestions": [
                { "id": "no_address", "label": "No address" }
              ]
            },
            {
              "id": "client_phone",
              "label": "Phone number",
              "type": "phone",
              "required": true,
              "placeholder": "+46 70 123 45 67"
            }
          ]
        }
      ]
    }
  },
  "success": true
}
```

### Frontend Submission

```json
{
  "message": "Clarification form submitted",
  "__interaction_response__": "int_clarify_create_order",
  "interaction_form": {
    "client_address": "Kungsgatan 5, Stockholm",
    "client_phone": "+46 70 123 45 67"
  }
}
```

### Alternate Submission Without Address

```json
{
  "message": "Clarification form submitted",
  "__interaction_response__": "int_clarify_create_order",
  "interaction_form": {
    "client_address": null,
    "client_phone": "+46 70 123 45 67"
  }
}
```

---

## Frontend Rendering Guidance

### Recommended UX

Render this as one blocking form surface, not multiple independent dialogs.

Good options:

- inline card in the transcript
- modal dialog
- side-panel form inside the AI panel

Recommended behavior:

1. Show interaction label as form title.
2. Render each field in order.
3. Respect `required` markers.
4. Render `suggestions` as quick chips/buttons below the input.
5. Allow submit only when required fields are valid.
6. Submit all values together in one request.

### Recommended UI Behavior For Suggestions

If a field has suggestions:

- clicking a suggestion can either:
  - insert that value into the field
  - set a semantic null/empty state

Example:

- suggestion: `No address`
- frontend may convert it to:
  - `null`
  - empty string
  - sentinel value only if backend contract explicitly allows it

Preferred backend-facing value:

- use `null` for omitted optional values
- do not send the visible label text as the actual stored value unless backend explicitly expects that

---

## Example Frontend Types

```ts
export type AIInteractionField = {
  id: string;
  label: string;
  type: "text" | "textarea" | "phone" | "email" | "number" | "date" | "datetime" | "select" | "boolean";
  required?: boolean;
  placeholder?: string;
  help_text?: string;
  default_value?: string | number | boolean | null;
  options?: Array<{ id: string; label: string }>;
  suggestions?: Array<{ id: string; label: string }>;
  validation?: {
    pattern?: "phone" | "email" | "postal_code";
    min?: number;
    max?: number;
    max_length?: number;
  };
};

export type AIInteraction = {
  id?: string;
  kind: "ui_action" | "continue_prompt" | "question" | "confirm";
  label: string;
  payload?: Record<string, unknown>;
  required?: boolean;
  response_mode?: "text" | "select" | "confirm" | "form";
  options?: Array<{ id: string; label: string }>;
  fields?: AIInteractionField[];
  hint?: string;
  disabled?: boolean;
};
```

---

## Example Frontend Submission Helper

```ts
async function submitInteractionForm(
  threadId: string,
  interactionId: string,
  values: Record<string, unknown>
) {
  return sendMessage(threadId, {
    message: "Clarification form submitted",
    __interaction_response__: interactionId,
    interaction_form: values,
  });
}
```

---

## Validation Expectations

Frontend should validate for UX.
Backend should validate for correctness.

Frontend validation examples:

- required fields must be filled before submit
- phone field should use phone formatting validation
- select field should submit only allowed option ids

Backend validation examples:

- required form fields must be present when declared required
- unknown field ids should be rejected or ignored explicitly
- values should be normalized before continuing workflow

---

## Backward Compatibility

This extension is additive.

Existing interactions remain valid:

- `question` + `select`
- `question` + `text`
- `continue_prompt`
- `confirm`

Frontend should add support for:

- `question` + `form`

If frontend does not yet support `response_mode = form`, recommended fallback behavior is:

1. Show the label and hint
2. Show a generic unsupported interaction state
3. Avoid silently dropping the interaction

---

## Recommended Backend Behavior

When this feature is implemented in backend:

1. Only one active blocking interaction should still exist at a time.
2. That single blocking interaction may collect multiple fields.
3. Resume request should process `interaction_form` as structured data.
4. Planner/tool layer should continue using normalized values, not free-text parsing.

This avoids the complexity of multiple simultaneous blocking questions while still solving the multi-missing-field problem.

---

## Comparison: Sequential Questions vs Clarification Form

### Sequential Questions

Pros:

- simpler backend state
- simpler single-answer contract

Cons:

- more turns
- slower completion
- worse UX for common data-entry workflows

### Clarification Form

Pros:

- fewer turns
- better UX
- better for create/update workflows
- easier to collect multiple missing values together

Cons:

- richer frontend implementation required
- backend needs structured form submission support

Recommendation:

- use clarification form for independent missing fields
- keep sequential questions for dependent branching decisions

---

## Backend Status

The backend contract support is now implemented for this pattern:

1. interaction schema supports `fields`
2. request payload supports `interaction_form`
3. route validates form-based question submissions
4. user turns persist structured form values
5. planner history replay includes structured form responses

What is not implemented yet:

1. backend generation of clarification-form interactions for specific workflows
2. create-order missing-field detection that emits `question + response_mode=form`

## Suggested Next Backend Steps

Next implementation step should include:

1. Add create-order clarification generation for missing address/phone
2. Add create/update workflow-specific missing-field detectors
3. Normalize submitted form values before continuing tool execution
4. Add integration tests for full form-generation happy path

---

## Version History

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-03-21 | Initial contract for multi-field clarification form proposal. |
| 1.1 | 2026-03-21 | Backend contract support implemented: schema fields, request payload, route validation, persistence, and planner-history replay. |