"""
Legacy placeholder for client-form-specific socket handlers.

Client form submit no longer emits a dedicated `client_form:submitted` socket
event. The submit flow now writes an `order_edited` outbox event and relies on
the standard order realtime relay (`realtime:event`).
"""
