from Delivery_app_BK.config.default import Config
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get("SQLALCHEMY_DATABASE_URI","postgresql://postgres:0698@localhost:5432/DeliveryApp")
    REDIS_URI = os.environ.get("REDIS_URI", "redis://localhost:6379/0")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
