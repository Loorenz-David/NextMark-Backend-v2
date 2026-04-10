from Delivery_app_BK.config.default import Config
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class TestingConfig(Config):
    TESTING = True
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or Config.SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
