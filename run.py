import eventlet
eventlet.monkey_patch()
from Delivery_app_BK import create_app
from Delivery_app_BK.socketio_instance import socketio

app = create_app()

if __name__ == '__main__':

    socketio.run(app, host='0.0.0.0', port=5050, debug=True, allow_unsafe_werkzeug=True)

