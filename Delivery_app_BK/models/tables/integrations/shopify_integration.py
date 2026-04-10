
from sqlalchemy import Column, Integer, String, Text, UniqueConstraint, ForeignKey
from sqlalchemy.orm import relationship
from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.utils import UTCDateTime
from datetime import datetime, timezone


class ShopifyIntegration(
    db.Model,
    TeamScopedMixin
):
    __tablename__ = "shopify_integrations"

    __table_args__ = (
        UniqueConstraint("team_id", "shop", name="uq_team_shop"),
    )

    id = Column(Integer, primary_key=True)

    shop = Column(String, nullable=False)
    access_token = Column(Text, nullable=False)
    # will add column: primary_location_id
    scopes = Column(String, nullable=False)

    connected_at = Column(UTCDateTime, nullable=False, default=datetime.now(timezone.utc))

    user_id = Column(
        Integer,
        ForeignKey("user.id")
    )

    user = relationship(
        "User",
        back_populates="shopify_integrations",
        lazy="selectin"
    )

    team = relationship(
        "Team",
        backref="shopify_integrations",
        lazy="selectin"
    )



class OAuthState(db.Model):
    __tablename__ = "oauth_states"

    __table_args__ = (
        UniqueConstraint("team_id", "state", name="uq_team_authstate"),
    )

    id = Column(Integer, primary_key=True)
    state = Column(String(128), unique=True, nullable=False)
    user_id = Column(Integer, nullable=False)
    team_id = Column(Integer, nullable=False)
    expires_at = Column(UTCDateTime, nullable=False)


class ShopifyWebhookEvents(db.Model):
    __tablename__ = "shopify_webhook_events"
    id = Column(Integer, primary_key=True)

    webhook_id = Column(String, unique=True, index=True)
    shop_domain = Column(String)
    topic = Column(String)
    status = Column(String)
    retry_counter = Column(Integer)
    dead_letter_attempt = Column(String)
    received_at = Column(UTCDateTime, default=datetime.now(timezone.utc))
