from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.utils import UTCDateTime


class ClientFormSettings(db.Model, TeamScopedMixin):
    """Per-team toggles controlling what the public client form renders."""

    __tablename__ = "client_form_settings"

    __table_args__ = (
        UniqueConstraint("team_id", name="uq_client_form_settings_team"),
    )

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)

    terms_enabled = Column(Boolean, nullable=False, default=False)
    require_acceptance = Column(Boolean, nullable=False, default=False)
    show_rules = Column(Boolean, nullable=False, default=True)
    show_media = Column(Boolean, nullable=False, default=True)

    updated_at = Column(
        UTCDateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    team = relationship("Team", backref="client_form_settings", lazy=True)
