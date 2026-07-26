# External-Form Socket Reliability — Backend Handoff (Acks + Presence)

## Context

The frontend realtime layer (`Front_end/packages/shared-realtime`) has been hardened so a
dropped or zombied socket self-heals without page reloads:

- a watchdog detects "connected" sockets that stopped receiving engine traffic (laptop
  sleep / network switch) and rebuilds them,
- `online` / tab-visible / window-focus events trigger an immediate reconnect with the
  current session token,
- the reconnect loop can no longer dead-end, and
- critical emits (`external_form:request_user`, `external_form:submit_user`) queue while
  disconnected and replay after the reconnect + room rejoin, instead of vanishing.

**The remaining gap is trust, and it is backend-shaped:** the relay handlers in
`Back_end/Delivery_app_BK/sockets/handlers/external_form.py` are fire-and-forget. The till
gets no confirmation that the request reached the server, and no way to know whether the
counter device is even in the team room. The UI currently says "sent" on pure hope.

Two additions close it. Both are backwards-compatible — no event renames, no changes to
existing payloads, older frontends simply ignore them.

## Ask 1 — Acknowledgement callbacks on the relay handlers

Socket.IO supports per-emit acknowledgements: when the client emits with a callback,
python-socketio delivers the **return value of the handler** as the ack. Add a return value
to these two handlers in `sockets/handlers/external_form.py`:

- `handle_external_form_request_user` (client event `external_form:request_user`)
- `handle_external_form_submit_user` (client event `external_form:submit_user`)

Return shape (same for both):

```python
return {
    "status": "relayed",
    "peers": <int>,   # sockets currently in the team's external_form room, excluding the sender
}
```

`peers` is the count of *other* members of `build_external_form_room(team_id)` at relay
time — with flask-socketio, the room membership is available via
`socketio.server.manager.rooms` for the default namespace. `peers == 0` means the
broadcast reached nobody (the counter device is not connected): the till can then tell the
staff member the device is offline instead of pretending the form was sent.

Keep the existing broadcast exactly as it is; the return value is purely additive. Handlers
that return nothing today implicitly ack `None`, so this cannot break any current caller.

## Ask 2 (recommended) — Presence broadcast for the team room

So the till can show "linked device online/offline" *before* the user clicks send:

- In `handle_external_form_join_user` and `handle_external_form_leave_user` (and on
  disconnect cleanup, where the server already removes the socket from its rooms), after
  membership changes, broadcast to the room:

```python
socketio.emit(
    "external_form:presence",
    {"members": <int>},   # current room size AFTER the change
    room=build_external_form_room(team_id),
)
```

- Add the event name to `sockets/contracts/realtime.py` alongside the existing
  `external_form:*` server events.
- No `skip_sid`: every member, including the one that just joined, should receive the
  fresh count.

Note: a socket that dies silently (network cut, no clean disconnect) leaves the room only
when the server's ping timeout reaps it, so presence may lag by roughly the ping cycle.
That is acceptable — the frontend treats presence as advisory and the ack from Ask 1 as
the authoritative per-send answer.

## Out of scope — do NOT change

- Event names or payload shapes of the existing `external_form:*` events.
- The progress relay (`external_form:progress_user`) — best-effort by design, no ack.
- The join/rejoin semantics — the frontend already replays joins on every reconnect.
- Socket token minting/TTL (`token_utils.py`) — recently changed, leave as is.

## Acceptance criteria

1. Emitting `external_form:request_user` with an ack callback receives
   `{"status": "relayed", "peers": <n>}`; emitting without a callback behaves exactly as
   today.
2. Same for `external_form:submit_user`.
3. `peers` excludes the emitting socket and reflects live room membership.
4. (Ask 2) Joining/leaving the room triggers `external_form:presence` with the updated
   member count to all room members.
5. Existing frontends (no ack callback, no presence listener) work unchanged.

## Frontend follow-up (ours, after this lands)

- Switch the till's request emit to emit-with-ack + timeout: `peers >= 1` → "sent",
  `peers == 0` → "device offline" warning with retry, timeout → connection error.
- Subscribe to `external_form:presence` to drive a live online/offline indicator on the
  send-to-device buttons and disable them honestly when the device is gone.
