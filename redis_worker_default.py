import os
import logging

from Delivery_app_BK import create_app
from Delivery_app_BK.services.infra.jobs.queues import get_named_queue
from Delivery_app_BK.services.infra.jobs.runtime import get_worker_class
from Delivery_app_BK.services.infra.redis import (
    assert_current_redis_available,
    describe_redis_uri,
    get_current_rq_redis_connection,
    get_redis_uri,
)


def _configure_logging() -> None:
    log_level_name = os.environ.get("APP_LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def main() -> None:
    _configure_logging()
    config_name = os.environ.get("APP_ENV", "development")
    app = create_app(config_name)

    with app.app_context():
        redis_uri = get_redis_uri()
        app.logger.info("Starting default Redis worker against %s.", describe_redis_uri(redis_uri))
        try:
            assert_current_redis_available(decode_responses=False)
        except Exception:
            app.logger.exception("Default Redis worker failed startup for %s.", describe_redis_uri(redis_uri))
            raise

        connection = get_current_rq_redis_connection()
        worker_class = get_worker_class()
        worker = worker_class(
            [
                get_named_queue("events", connection=connection),
                get_named_queue("default", connection=connection),
                get_named_queue("realtime", connection=connection),
            ],
            connection=connection,
            name=os.environ.get("RQ_WORKER_NAME", "worker-default"),
        )
        worker.work(burst=False)


if __name__ == "__main__":
    main()
