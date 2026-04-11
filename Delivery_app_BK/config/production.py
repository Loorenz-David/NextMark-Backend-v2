from Delivery_app_BK.config.default import Config
import os
from datetime import timedelta

class ProductionConfig(Config):
    DEBUG = False

    # SQLAlchemy production database (RDS)
    SQLALCHEMY_DATABASE_URI = os.environ.get("SQLALCHEMY_DATABASE_URI")


    # Token expiration
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)