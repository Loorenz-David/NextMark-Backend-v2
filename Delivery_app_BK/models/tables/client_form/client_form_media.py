from sqlalchemy import Boolean, Column, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship, validates

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.services.domain.client_form.media_placement import (
    ALLOWED_MEDIA_PLACEMENTS,
)


class ClientFormMedia(db.Model, TeamScopedMixin):
    """An image rendered at a named slot on the public client form."""

    __tablename__ = "client_form_media"

    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "placement",
            "position",
            name="uq_client_form_media_team_placement_position",
        ),
    )

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)

    placement = Column(String, nullable=False, index=True)
    position = Column(Integer, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)

    url = Column(String, nullable=False)
    # Reserved for when uploads land — lets the URL be regenerated without a data migration.
    storage_key = Column(String, nullable=True)
    # Accessibility text for the image itself, distinct from the visible caption below.
    alt_text = Column(String, nullable=True)
    link_url = Column(String, nullable=True)

    # Optional visible caption. The image stays the required part — a plain banner
    # carries neither of these.
    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)

    team = relationship("Team", backref="client_form_media", lazy=True)

    @validates("placement")
    def validate_placement(self, key, value):
        if value not in ALLOWED_MEDIA_PLACEMENTS:
            raise ValidationFailed(
                f"Invalid placement '{value}'. "
                f"Allowed values: {sorted(ALLOWED_MEDIA_PLACEMENTS)}"
            )
        return value

    @validates("position")
    def validate_position(self, key, value):
        if value is None or isinstance(value, bool) or not isinstance(value, int):
            raise ValidationFailed("Media position must be an integer.")
        if value < 0:
            raise ValidationFailed("Media position cannot be negative.")
        return value

    @validates("url")
    def validate_url(self, key, value):
        if not isinstance(value, str) or not value.strip():
            raise ValidationFailed("Media url is required.")
        return value.strip()
