from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from Delivery_app_BK.models.mixins.external_integrations.twilio_mixin import SMSMixin

from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin


class TwilioMod(db.Model, TeamScopedMixin, SMSMixin):
    __tablename__ = "twilio_mod"

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)
    twilio_account_sid = Column(String, nullable=False)
    twilio_api_key_sid = Column(String, nullable=False)
    twilio_api_key_secret_encrypted = Column(String, nullable=False)
    sender_number = Column(String, nullable=False)

    team = relationship(
        "Team",
        backref="twilio_settings",
        lazy=True
    )
