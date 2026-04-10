from __future__ import annotations
from typing import Optional, Dict, Any, List
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# V1 schemas (kept for backward compat)
# ---------------------------------------------------------------------------

class ToolCall(BaseModel):
    tool: str
    parameters: Dict[str, Any] = {}


class PlannerStep(BaseModel):
    type: str  # "tool" | "final"
    tool: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


class PlannerState(BaseModel):
    steps: List[Dict[str, Any]] = []


class AIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    steps: List[Dict[str, Any]] = []


# ---------------------------------------------------------------------------
# V2 thread schemas
# ---------------------------------------------------------------------------

class AIAction(BaseModel):
    id: Optional[str] = None
    type: str                          # navigate | apply_order_filters | copy_text | open_settings
    label: str
    payload: Optional[Dict[str, Any]] = None
    hint: Optional[str] = None
    disabled: Optional[bool] = None


class AIToolTraceEntry(BaseModel):
    id: str
    tool: str
    status: str                        # "success" | "error"
    summary: str
    params: Dict[str, Any] = {}
    result: Dict[str, Any] = {}


class AIThreadTurn(BaseModel):
    id: str
    thread_id: str
    role: str                          # "user" | "assistant" | "tool"
    content: str
    created_at: str                    # ISO-8601

    tool_name: Optional[str] = None
    tool_params: Optional[Dict[str, Any]] = None
    tool_result: Optional[Dict[str, Any]] = None

    actions: Optional[List[AIAction]] = None
    tool_trace: Optional[List[AIToolTraceEntry]] = None
    data: Optional[Dict[str, Any]] = None
    status_label: Optional[str] = None


class AIThreadMetadata(BaseModel):
    thread_id: str
    user_id: int
    app_scope: str
    session_scope_id: Optional[str] = None
    current_workspace: Optional[str] = None
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Route DTOs
# ---------------------------------------------------------------------------

class AIThreadCreateResponse(BaseModel):
    thread_id: str


class AIThreadMessageRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None


class AIThreadMessagePayload(BaseModel):
    role: str
    content: str
    status_label: Optional[str] = None
    actions: List[AIAction] = []
    tool_trace: List[AIToolTraceEntry] = []
    data: Optional[Dict[str, Any]] = None


class AIThreadMessageResponse(BaseModel):
    thread_id: str
    message: AIThreadMessagePayload


class AIThreadGetResponse(BaseModel):
    thread_id: str
    messages: List[AIThreadTurn] = []

