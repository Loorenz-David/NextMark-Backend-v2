from Delivery_app_BK.socketio_instance import socketio
from Delivery_app_BK.sockets.connection.handlers import handle_connect, handle_disconnect
from Delivery_app_BK.sockets.contracts.realtime import (
    CLIENT_EVENT_DRIVER_LOCATION_PUBLISH,
    CLIENT_EVENT_EXTERNAL_FORM_JOIN_USER,
    CLIENT_EVENT_EXTERNAL_FORM_LEAVE_USER,
    CLIENT_EVENT_NOTIFICATION_MARK_READ,
    CLIENT_EVENT_EXTERNAL_FORM_REQUEST_USER,
    CLIENT_EVENT_EXTERNAL_FORM_SUBMIT_USER,
    CLIENT_EVENT_SUBSCRIBE,
    CLIENT_EVENT_UNSUBSCRIBE,
)
from Delivery_app_BK.sockets.handlers.external_form import (
    handle_external_form_join_user,
    handle_external_form_leave_user,
    handle_external_form_request_user,
    handle_external_form_submit_user,
)
from Delivery_app_BK.sockets.notifications import handle_notification_mark_read
from Delivery_app_BK.sockets.handlers.subscriptions import handle_subscribe, handle_unsubscribe
from Delivery_app_BK.sockets.telemetry.driver_live import publish_driver_location

_registered = False


def register_socket_handlers() -> None:
    global _registered
    if _registered:
        return

    socketio.on_event("connect", handle_connect)
    socketio.on_event("disconnect", handle_disconnect)
    socketio.on_event(CLIENT_EVENT_SUBSCRIBE, handle_subscribe)
    socketio.on_event(CLIENT_EVENT_UNSUBSCRIBE, handle_unsubscribe)
    socketio.on_event(CLIENT_EVENT_DRIVER_LOCATION_PUBLISH, publish_driver_location)
    socketio.on_event(CLIENT_EVENT_NOTIFICATION_MARK_READ, handle_notification_mark_read)
    socketio.on_event(CLIENT_EVENT_EXTERNAL_FORM_JOIN_USER, handle_external_form_join_user)
    socketio.on_event(CLIENT_EVENT_EXTERNAL_FORM_LEAVE_USER, handle_external_form_leave_user)
    socketio.on_event(CLIENT_EVENT_EXTERNAL_FORM_SUBMIT_USER, handle_external_form_submit_user)
    socketio.on_event(CLIENT_EVENT_EXTERNAL_FORM_REQUEST_USER, handle_external_form_request_user)
    _registered = True
