import json

from Delivery_app_BK.ai import planner
from Delivery_app_BK.ai.schemas import PlannerFinalStep


class _DummyProvider:
    name = "dummy"

    def complete(self, system: str, user: str) -> str:
        return '{"type": "final", "message": "ok"}'


def test_get_next_step_does_not_append_duplicate_tail_user(monkeypatch):
    captured = {}

    def _fake_complete_with_history(_provider, messages):
        captured["messages"] = messages
        return json.dumps({"type": "final", "message": "ok"})

    monkeypatch.setattr(planner, "_complete_with_history", _fake_complete_with_history)

    same_input = "how many of those are active"
    history = [{"role": "user", "content": same_input}]

    step = planner.get_next_step(same_input, history, _DummyProvider())

    assert isinstance(step, PlannerFinalStep)
    assert step.type == "final"
    user_messages = [m for m in captured["messages"] if m.get("role") == "user"]
    assert len(user_messages) == 1
    assert user_messages[0]["content"] == same_input


def test_get_next_step_appends_current_user_when_tail_is_different(monkeypatch):
    captured = {}

    def _fake_complete_with_history(_provider, messages):
        captured["messages"] = messages
        return json.dumps({"type": "final", "message": "ok"})

    monkeypatch.setattr(planner, "_complete_with_history", _fake_complete_with_history)

    history = [
        {"role": "user", "content": "how many deliveries for uppsala"},
        {"role": "assistant", "content": '{"type":"final","message":"Found 8 deliveries."}'},
    ]

    current_input = "how many of those are active"
    step = planner.get_next_step(current_input, history, _DummyProvider())

    assert isinstance(step, PlannerFinalStep)
    assert step.type == "final"
    user_messages = [m for m in captured["messages"] if m.get("role") == "user"]
    assert user_messages[-1]["content"] == current_input
