from types import SimpleNamespace

from Delivery_app_BK.services.commands.route_plan.plan_states import update_plan_state as module


class _DummyTransaction:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_update_plan_state_updates_all_loaded_plans(monkeypatch):
    plan_a = SimpleNamespace(id=1, state_id=1)
    plan_b = SimpleNamespace(id=2, state_id=1)

    monkeypatch.setattr(
        module,
        "parse_update_plan_state_request",
        lambda plan_ids, state_id: SimpleNamespace(plan_ids=[1, 2], state_id=state_id),
    )
    monkeypatch.setattr(
        module,
        "_resolve_plans_for_update",
        lambda ctx, plan_ids: [plan_a, plan_b],
    )
    monkeypatch.setattr(module.db.session, "begin", lambda: _DummyTransaction())

    result = module.update_plan_state(ctx=SimpleNamespace(), plan_ids=[1, 2], state_id=2)

    assert plan_a.state_id == 2
    assert plan_b.state_id == 2
    assert result == [1, 2]
