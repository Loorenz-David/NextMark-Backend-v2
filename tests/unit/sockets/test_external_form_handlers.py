from types import SimpleNamespace

import pytest

import Delivery_app_BK.sockets.handlers.external_form as external_form
from Delivery_app_BK.sockets.contracts.realtime import (
    SERVER_EVENT_EXTERNAL_FORM_PRESENCE,
    SERVER_EVENT_EXTERNAL_FORM_RECEIVED,
    SERVER_EVENT_EXTERNAL_FORM_REQUESTED,
)

TEAM_ID = 42
ROOM = f"external_form:{TEAM_ID}"
CLAIMS = {"active_team_id": TEAM_ID, "user_id": 7}


@pytest.fixture
def emitted(monkeypatch):
    calls = []

    def fake_emit(event, payload, **kwargs):
        calls.append({"event": event, "payload": payload, **kwargs})

    monkeypatch.setattr(external_form.socketio, "emit", fake_emit)
    return calls


def _install_rooms(monkeypatch, members, *, sid="sid-sender"):
    rooms = {"/": {ROOM: {member: member for member in members}}}
    server = SimpleNamespace(
        manager=SimpleNamespace(rooms=rooms),
        rooms=lambda sid: [
            room for room, participants in rooms["/"].items() if sid in participants
        ],
    )
    monkeypatch.setattr(external_form.socketio, "server", server, raising=False)
    monkeypatch.setattr(external_form, "request", SimpleNamespace(sid=sid))
    return server


def test_request_user_acks_with_peer_count_excluding_sender(monkeypatch, emitted):
    _install_rooms(monkeypatch, ["sid-sender", "sid-counter", "sid-other"])

    ack = external_form.handle_external_form_request_user.__wrapped__(
        CLAIMS, {"request_data": {"order_id": 1}}
    )

    assert ack == {"status": "relayed", "peers": 2}
    assert emitted == [
        {
            "event": SERVER_EVENT_EXTERNAL_FORM_REQUESTED,
            "payload": {"request_data": {"order_id": 1}, "requested_by": 7},
            "room": ROOM,
            "skip_sid": "sid-sender",
        }
    ]


def test_request_user_acks_zero_peers_when_room_has_only_sender(monkeypatch, emitted):
    _install_rooms(monkeypatch, ["sid-sender"])

    ack = external_form.handle_external_form_request_user.__wrapped__(CLAIMS, {})

    assert ack == {"status": "relayed", "peers": 0}


def test_submit_user_acks_with_peer_count(monkeypatch, emitted):
    _install_rooms(monkeypatch, ["sid-sender", "sid-counter"])

    ack = external_form.handle_external_form_submit_user.__wrapped__(
        CLAIMS, {"form_data": {"name": "Ann"}}
    )

    assert ack == {"status": "relayed", "peers": 1}
    assert emitted[0]["event"] == SERVER_EVENT_EXTERNAL_FORM_RECEIVED
    assert emitted[0]["skip_sid"] == "sid-sender"


def test_submit_user_without_form_data_acks_none_and_emits_nothing(monkeypatch, emitted):
    _install_rooms(monkeypatch, ["sid-sender", "sid-counter"])

    ack = external_form.handle_external_form_submit_user.__wrapped__(CLAIMS, {})

    assert ack is None
    assert emitted == []


def test_join_broadcasts_presence_with_count_including_joiner(monkeypatch, emitted):
    server = _install_rooms(monkeypatch, ["sid-counter"], sid="sid-joiner")

    def fake_join_room(room, sid=None):
        server.manager.rooms["/"][room][sid] = sid

    monkeypatch.setattr(external_form, "join_room", fake_join_room)

    external_form.handle_external_form_join_user.__wrapped__(CLAIMS, {})

    assert emitted == [
        {
            "event": SERVER_EVENT_EXTERNAL_FORM_PRESENCE,
            "payload": {"members": 2},
            "room": ROOM,
        }
    ]


def test_leave_broadcasts_presence_with_count_after_removal(monkeypatch, emitted):
    server = _install_rooms(monkeypatch, ["sid-sender", "sid-counter"])

    def fake_leave_room(room, sid=None):
        server.manager.rooms["/"][room].pop(sid, None)

    monkeypatch.setattr(external_form, "leave_room", fake_leave_room)

    external_form.handle_external_form_leave_user.__wrapped__(CLAIMS, {})

    assert emitted == [
        {
            "event": SERVER_EVENT_EXTERNAL_FORM_PRESENCE,
            "payload": {"members": 1},
            "room": ROOM,
        }
    ]


def test_disconnect_broadcasts_presence_excluding_dying_sid(monkeypatch, emitted):
    _install_rooms(monkeypatch, ["sid-dying", "sid-counter"], sid="sid-dying")

    external_form.broadcast_external_form_presence_on_disconnect("sid-dying")

    assert emitted == [
        {
            "event": SERVER_EVENT_EXTERNAL_FORM_PRESENCE,
            "payload": {"members": 1},
            "room": ROOM,
        }
    ]


def test_disconnect_ignores_sockets_outside_external_form_rooms(monkeypatch, emitted):
    server = _install_rooms(monkeypatch, [], sid="sid-dying")
    server.manager.rooms["/"] = {"team:42:orders": {"sid-dying": "sid-dying"}}

    external_form.broadcast_external_form_presence_on_disconnect("sid-dying")

    assert emitted == []
