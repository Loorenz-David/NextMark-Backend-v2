from sqlalchemy import Boolean, Column, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship, validates

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin


class ClientFormRule(db.Model, TeamScopedMixin):
    """An ordered delivery-rule entry shown on the public client form."""

    __tablename__ = "client_form_rule"

    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "position",
            name="uq_client_form_rule_team_position",
        ),
    )

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)

    position = Column(Integer, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)

    title = Column(String, nullable=False)
    body = Column(Text, nullable=True)
    icon = Column(String, nullable=True)
    image_url = Column(String, nullable=True)

    team = relationship("Team", backref="client_form_rules", lazy=True)

    @validates("position")
    def validate_position(self, key, value):
        if value is None or isinstance(value, bool) or not isinstance(value, int):
            raise ValidationFailed("Rule position must be an integer.")
        if value < 0:
            raise ValidationFailed("Rule position cannot be negative.")
        return value

    @validates("title")
    def validate_title(self, key, value):
        if not isinstance(value, str) or not value.strip():
            raise ValidationFailed("Rule title is required.")
        return value.strip()
