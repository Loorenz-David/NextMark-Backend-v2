import eventlet
eventlet.monkey_patch(all=True)

from Delivery_app_BK import create_app
from Delivery_app_BK.socketio_instance import socketio

application = create_app("production")  


