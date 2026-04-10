from __future__ import annotations

from flask import Flask
from flask_jwt_extended import create_access_token

from Delivery_app_BK.ai import orchestrator as ai_orchestrator
from Delivery_app_BK.ai.schemas import AIThreadMetadata
from Delivery_app_BK.routers.api_v2 import ai as ai_route
from Delivery_app_BK.routers.utils.jwt_handler import jwt


def _build_app() -> Flask:
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        DEBUG=True,
        JWT_SECRET_KEY="test-secret",
    )
    jwt.init_app(app)
    app.register_blueprint(ai_route.ai_bp, url_prefix="/api_v2/ai")
    return app


def _auth_headers(app: Flask) -> dict[str, str]:
    claims = {
        "user_id": 1,
        "team_id": 10,
        "active_team_id": 10,
        "base_role_id": 2,
        "app_scope": "admin",
        "session_scope_id": "sess_123",
        "time_zone": "Europe/Stockholm",
        "default_country_code": "SE",
    }
    with app.app_context():
        token = create_access_token(identity="1", additional_claims=claims)
    return {"Authorization": f"Bearer {token}"}


def _install_thread_store_stubs(monkeypatch):
    stored_turns: list = []

    monkeypatch.setattr(ai_route, "assert_thread_access", lambda *args, **kwargs: None)
    monkeypatch.setattr(ai_route, "append_turn", lambda thread_id, turn: stored_turns.append(turn))
    monkeypatch.setattr(ai_route, "list_turns", lambda thread_id: [])
    monkeypatch.setattr(ai_route, "list_turns_for_topic", lambda thread_id, topic_id: [])
    monkeypatch.setattr(ai_route, "set_active_topic_session", lambda thread_id, topic_id: (topic_id, False))
    monkeypatch.setattr(ai_route.thread_store, "get_turn_awaiting_response", lambda thread_id: None)
    monkeypatch.setattr(ai_route.thread_store, "clear_turn_awaiting_response", lambda thread_id, turn_id: None)

    return stored_turns


def test_capability_policy_manual_mode_is_resolved_and_emitted_in_response(monkeypatch):
    app = _build_app()
    client = app.test_client()
    _install_thread_store_stubs(monkeypatch)

    captured = {}
    monkeypatch.setattr(
        ai_route,
        "handle_ai_request_with_thread",
        lambda ctx, message, prior_turns, **kwargs: (
            captured.update({"kwargs": kwargs})
            or ai_orchestrator.OrchestratorResult(
                final_message="Statistics capability selected.",
                tool_turns=[],
                success=True,
            )
        ),
    )

    response = client.post(
        "/api_v2/ai/threads/thr_123/messages",
        json={
            "message": "show me weekly performance",
            "context": {"capability_mode": "manual", "capability_id": "statistics"},
        },
        headers=_auth_headers(app),
    )

    assert response.status_code == 200
    assert captured["kwargs"]["capability_name"] == "statistics"

    message_data = response.get_json()["data"]["message"]["data"]
    assert message_data["resolved_capability_mode"] == "manual"
    assert message_data["resolved_capability_id"] == "statistics"
    assert message_data["tool_policy"] == "readonly"


def test_capability_policy_rejects_manual_mode_without_capability_id(monkeypatch):
    app = _build_app()
    client = app.test_client()
    _install_thread_store_stubs(monkeypatch)

    response = client.post(
        "/api_v2/ai/threads/thr_123/messages",
        json={"message": "show stats", "context": {"capability_mode": "manual"}},
        headers=_auth_headers(app),
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["code"] == "capability_policy_missing_id"


def test_capability_policy_rejects_unknown_manual_capability_id(monkeypatch):
    app = _build_app()
    client = app.test_client()
    _install_thread_store_stubs(monkeypatch)

    response = client.post(
        "/api_v2/ai/threads/thr_123/messages",
        json={
            "message": "show stats",
            "context": {"capability_mode": "manual", "capability_id": "not_real"},
        },
        headers=_auth_headers(app),
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["code"] == "capability_policy_unknown_id"


def test_capability_policy_fallback_auto_on_unknown_manual_capability_id(monkeypatch):
    app = _build_app()
    app.config.update(AI_CAPABILITY_POLICY_INVALID_INPUT_BEHAVIOR="fallback_auto")
    client = app.test_client()
    _install_thread_store_stubs(monkeypatch)

    captured = {}
    monkeypatch.setattr(
        ai_route,
        "handle_ai_request_with_thread",
        lambda ctx, message, prior_turns, **kwargs: (
            captured.update({"kwargs": kwargs})
            or ai_orchestrator.OrchestratorResult(
                final_message="Fallback auto capability selected.",
                tool_turns=[],
                success=True,
            )
        ),
    )

    response = client.post(
        "/api_v2/ai/threads/thr_123/messages",
        json={
            "message": "show performance this week",
            "context": {"capability_mode": "manual", "capability_id": "not_real"},
        },
        headers=_auth_headers(app),
    )

    assert response.status_code == 200
    # Auto-routing hint for performance analytics should resolve to statistics.
    assert captured["kwargs"]["capability_name"] == "statistics"

    message_data = response.get_json()["data"]["message"]["data"]
    assert message_data["requested_capability_mode"] == "auto"
    assert message_data["requested_capability_id"] is None
    assert message_data["resolved_capability_mode"] == "auto"
    assert message_data["resolved_capability_id"] == "statistics"
    assert "capability_id_unknown_fallback_auto" in (message_data.get("policy_warnings") or [])


def test_capability_policy_thread_lock_rejects_resolved_mismatch(monkeypatch):
    app = _build_app()
    app.config.update(AI_CAPABILITY_POLICY_THREAD_LOCK_ENABLED=True)
    client = app.test_client()
    _install_thread_store_stubs(monkeypatch)

    monkeypatch.setattr(
        ai_route.thread_store,
        "get_thread_metadata",
        lambda thread_id: AIThreadMetadata(
            thread_id=thread_id,
            user_id=1,
            app_scope="admin",
            session_scope_id="sess_123",
            current_workspace="/",
            active_topic="logistics",
            topic_stack=[],
            created_at="2026-03-22T10:00:00Z",
            updated_at="2026-03-22T10:00:00Z",
        ),
    )

    response = client.post(
        "/api_v2/ai/threads/thr_123/messages",
        json={
            "message": "show performance",
            "context": {"capability_mode": "manual", "capability_id": "statistics"},
        },
        headers=_auth_headers(app),
    )

    assert response.status_code == 409
    payload = response.get_json()
    assert payload["code"] == "capability_policy_thread_locked"
