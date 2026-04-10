import os
import time
from uuid import uuid4

from Delivery_app_BK import create_app
from Delivery_app_BK.services.infra.events.dispatcher import dispatch_pending_events
from Delivery_app_BK.services.infra.redis import assert_current_redis_available, describe_redis_uri, get_redis_uri


def main() -> None:
    config_name = os.environ.get("APP_ENV", "development")
    app = create_app(config_name)
    dispatcher_id = os.environ.get("DISPATCHER_ID", f"dispatcher-{uuid4()}")

    with app.app_context():
        redis_uri = get_redis_uri()
        app.logger.info("Starting Redis dispatcher against %s.", describe_redis_uri(redis_uri))
        try:
            assert_current_redis_available(decode_responses=False)
        except Exception:
            app.logger.exception("Redis dispatcher failed startup for %s.", describe_redis_uri(redis_uri))
            raise
        try:
            while True:
                
                claimed = dispatch_pending_events(
                    dispatcher_id=dispatcher_id,
                    batch_size=app.config.get("REDIS_DISPATCH_BATCH_SIZE", 50),
                    lease_seconds=app.config.get("REDIS_DISPATCHER_LEASE_SECONDS", 120),
                )

                time.sleep(1 if claimed else 3)
        except Exception as e:
            app.logger.critical("Dispatcher loop failed: %s", str(e), exc_info=True)
            raise

if __name__ == "__main__":
    main()
