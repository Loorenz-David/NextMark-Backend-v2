from flask_socketio import SocketIO

# Shared Socket.IO instance configured with permissive CORS.
# The app factory in Delivery_app_BK/__init__.py will call socketio.init_app(app).

""" if user usage increases to more than 20+ thousand we must look at increasing
    the pings and timeouts on the client side
"""
socketio = SocketIO(async_mode="eventlet", 
                    cors_allowed_headers=["Authorization"],
                    cors_allowed_origins="*",
                   
                    )
