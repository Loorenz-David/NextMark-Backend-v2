from types import SimpleNamespace

from Delivery_app_BK.services.domain.user import resolve_user_role_id_for_team
from Delivery_app_BK.services.queries.order import get_order_event_history as module


def _user(**overrides):
    values = {
        "id": 5,
        "username": "dana",
        "team_id": 1,
        "user_role_id": 10,
        "team_workspace_team_id": None,
        "team_workspace_role_id": None,
        "primals_team_id": 1,
        "primals_role_id": 10,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _role(role_id, role_name, base_role_name):
    return SimpleNamespace(
        id=role_id,
        role_name=role_name,
        base_role=SimpleNamespace(role_name=base_role_name),
    )


def test_role_resolves_from_active_team():
    assert resolve_user_role_id_for_team(_user(), 1) == 10


def test_role_resolves_from_team_workspace_snapshot():
    user = _user(team_workspace_team_id=2, team_workspace_role_id=20)
    assert resolve_user_role_id_for_team(user, 2) == 20


def test_role_resolves_from_personal_team_while_in_another_workspace():
    user = _user(team_id=2, user_role_id=20)
    assert resolve_user_role_id_for_team(user, 1) == 10


def test_role_is_none_for_unrelated_team():
    assert resolve_user_role_id_for_team(_user(), 99) is None


def test_actor_serializes_username_and_role():
    event = SimpleNamespace(actor=_user(), team_id=1)
    roles_by_id = {10: _role(10, "Dispatcher", "ASSISTANT")}

    assert module._serialize_actor(event, roles_by_id) == {
        "id": 5,
        "username": "dana",
        "role_name": "Dispatcher",
        "base_role": "assistant",
    }


def test_actor_without_resolvable_role_keeps_username():
    event = SimpleNamespace(actor=_user(), team_id=99)

    assert module._serialize_actor(event, {}) == {
        "id": 5,
        "username": "dana",
        "role_name": None,
        "base_role": None,
    }


def test_system_event_has_no_actor():
    event = SimpleNamespace(actor=None, team_id=1)
    assert module._serialize_actor(event, {}) is None
