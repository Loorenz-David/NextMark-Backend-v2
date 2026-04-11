
import os
from datetime import timedelta

# Third-part dependencies
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_migrate import Migrate
from Delivery_app_BK.socketio_instance import socketio
from sqlalchemy.orm import configure_mappers


from Delivery_app_BK.routers.utils.compress_request import compress_payload
from Delivery_app_BK.routers.utils.decompress_request import decompress_request



# Local application imports 
from Delivery_app_BK.models import db
from Delivery_app_BK.routers.utils.jwt_handler import jwt
from Delivery_app_BK.services.infra.redis import assert_redis_available, describe_redis_uri


# configuration map
config_map = {
    "development": "Delivery_app_BK.config.development.DevelopmentConfig",
    "testing": "Delivery_app_BK.config.testing.TestingConfig",
    "production": "Delivery_app_BK.config.production.ProductionConfig",
}



# app factory
def create_app(config_name="development"):

    app = Flask(__name__)
    
    # app configuration
    app.config.from_object(config_map.get(config_name))

    frontend_origins = os.environ.get("FRONTEND_ORIGINS", "http://localhost:5173").split(',')

    CORS(
        app, 
        supports_credentials=True,
        resources={r"/*": {"origins": frontend_origins}}, 
        allow_headers=["Content-Type", "Authorization"],
        expose_headers="*",
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
        )

    # init app object
    db.init_app(app)
    jwt.init_app(app)
    Migrate(app, db)
    _initialize_socketio(app, frontend_origins)


    from .routers.api_v2 import register_v2_blueprints
    register_v2_blueprints(app)
    from .routers.webhooks import register_webhook_blueprints
    register_webhook_blueprints(app)

    from Delivery_app_BK.sockets.register import register_socket_handlers
    register_socket_handlers()

    with app.app_context():

        from Delivery_app_BK.services.infra.events import get_event_bus
        get_event_bus()

    configure_mappers()

    
    @app.before_request
    def decompress_response():
        return decompress_request()

    @app.after_request
    def compress_response( response ):

        if request.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        if request.endpoint == "api_v2_integration_shopify.shopify_app_home":
            response.headers["X-Frame-Options"] = "ALLOWALL"
            response.headers["Content-Security-Policy"] = (
                "frame-ancestors https://admin.shopify.com https://*.myshopify.com"
            )
            return response

        compressed_response = compress_payload( response )

        return compressed_response
    

    @app.route("/", methods=["GET"])
    def health():
        from sqlalchemy import text
        from Delivery_app_BK.services.infra.redis import assert_redis_available

        health_status = {
            "status": "ok",
            "services": {}
        }

        overall_ok = True

        # --- Database check ---
        try:
            db.session.execute(text("SELECT 1"))
            health_status["services"]["db"] = "ok"
        except Exception as e:
            health_status["services"]["db"] = f"error: {str(e)}"
            overall_ok = False

        # --- Redis check ---
        # --- Redis check ---
        try:
            redis_uri = app.config.get("REDIS_URI", "")
            if not redis_uri:
                raise RuntimeError("REDIS_URI not configured")

            assert_redis_available(redis_uri)
            health_status["services"]["redis"] = "ok"
        except Exception as e:
            health_status["services"]["redis"] = f"error: {str(e)}"
            overall_ok = False

        # --- Final status ---
        health_status["status"] = "ok" if overall_ok else "degraded"

        return health_status, (200 if overall_ok else 503)


def _initialize_socketio(app: Flask, frontend_origins: list[str]) -> None:
    redis_uri = app.config.get("REDIS_URI", "")
    socketio_kwargs = {
        "cors_allowed_origins": frontend_origins,
    }

    if not redis_uri:
        app.logger.warning("Socket.IO initialized without Redis message queue because REDIS_URI is not configured.")
        socketio.init_app(app, **socketio_kwargs)
        return

    try:
        assert_redis_available(redis_uri, decode_responses=False)
        socketio.init_app(
            app,
            **socketio_kwargs,
            message_queue=redis_uri,
            channel="nextmark-socketio",
        )
        app.logger.info("Socket.IO initialized with Redis message queue at %s.", describe_redis_uri(redis_uri))
    except Exception as exc:
        app.logger.warning(
            "Socket.IO Redis message queue unavailable (%s). Falling back to in-process Socket.IO. Error: %s",
            describe_redis_uri(redis_uri),
            exc,
        )
        socketio.init_app(app, **socketio_kwargs)
