from __future__ import annotations

import os
import sys
from functools import wraps

from rq import SimpleWorker, Worker

from Delivery_app_BK import create_app


def with_app_context(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        app = create_app()
        with app.app_context():
            return fn(*args, **kwargs)

    return wrapper


def get_worker_class():
    if os.environ.get("RQ_USE_SIMPLE_WORKER") == "1":
        return SimpleWorker
    if sys.platform == "darwin" and os.environ.get("APP_ENV", "development") == "development":
        return SimpleWorker
    return Worker
