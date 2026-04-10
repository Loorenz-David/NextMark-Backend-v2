from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship

from Delivery_app_BK.models.mixins.external_integrations.smtp_mixin import SMTPMixin

from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin


class EmailSMTP(db.Model, TeamScopedMixin, SMTPMixin):
    __tablename__ = "email_smtp"

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)
    smtp_server = Column(String, nullable=False) # for gmail smtp.gmail.com
    smtp_port = Column(Integer, default=587) # Default to 587 for TLS
    smtp_username = Column(String, nullable=False)
    smtp_password = Column(String, nullable=False)
    use_tls = Column(Boolean, default=True)
    use_ssl = Column(Boolean, default=False)
    max_per_session = Column(Integer, default=50)

    team = relationship(
        "Team",
        backref="email_settings",
        lazy=True
    )
