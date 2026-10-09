from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Index, Integer, String, text
from sqlalchemy.orm import relationship, validates

from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.utils import UTCDateTime
from Delivery_app_BK.services.domain.client_form.redirect_url import (
    MAX_REDIRECT_URL_LENGTH,
    normalize_redirect_label,
    normalize_redirect_url,
)


class ClientFormRedirect(db.Model, TeamScopedMixin):
    """A saved page the public client form can send the customer to after submit.

    A team keeps a list of these and marks at most one active; with none active
    the form stays on its confirmation screen.
    """

    __tablename__ = "client_form_redirect"

    __table_args__ = (
        Index("ix_client_form_redirect_team_id", "team_id"),
        Index(
            "uix_client_form_redirect_active_team",
            "team_id",
            unique=True,
            postgresql_where=text("is_active IS TRUE"),
        ),
    )

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)

    label = Column(String, nullable=False)
    url = Column(String(MAX_REDIRECT_URL_LENGTH), nullable=False)
    is_active = Column(Boolean, nullable=False, default=False)

    created_at = Column(
        UTCDateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        UTCDateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    team = relationship("Team", backref="client_form_redirects", lazy=True)

    @validates("label")
    def validate_label(self, key, value):
        return normalize_redirect_label(value)

    @validates("url")
    def validate_url(self, key, value):
        return normalize_redirect_url(value)
