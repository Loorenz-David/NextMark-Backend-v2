# Thirs-party dependencies
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Column, Integer, String, JSON
from datetime import datetime, timezone

# Local application imports
from Delivery_app_BK.models import db
from Delivery_app_BK.models.utils import UTCDateTime


class Team(db.Model):
    __tablename__ = "team"
    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)
    name = Column(String, nullable=False, index=True)
    created_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc))

    # a dictionary use by the front end to notify the user that there is configuration missing
    missing_to_configure = Column(JSONB().with_variant(JSON, "sqlite"))

    # a dictionary made to check if the user has a valid subscription to use some properties
    # last thing to develop
    subscription = Column(JSONB().with_variant(JSON, "sqlite"))
    time_zone = Column(String(64), nullable=False, default="UTC") # IANA timezone identifier
    default_country_code = Column(String(2), nullable=True)  # ISO 3166-1 alpha-2 geocoding hint
    default_city_key = Column(String(64), nullable=True)  # normalized city key used for zone-scoped defaults
