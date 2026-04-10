# Third-party dependecies
from sqlalchemy.orm import validates
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Column, Integer, String, JSON, Boolean, UniqueConstraint
from Delivery_app_BK.models import db

# Local application imports
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.tables.items.item_type import type_property_association


class ItemProperty(db.Model, TeamScopedMixin):
    __tablename__ = "item_property"
    __table_args__ = (
        UniqueConstraint("team_id", "name", name="uq_itemproperty_team_name"),
    )

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)
    name = Column(String, nullable=False, index=True)
    field_type = Column(String, default="text")
    options = Column(JSONB().with_variant(JSON, "sqlite"))
    required = Column(Boolean, nullable=False)
    is_system = Column(Boolean, default=False, index=True)

    item_types = db.relationship(
        "ItemType",
        secondary=type_property_association,
        back_populates="properties"
    )

    team = db.relationship(
        "Team",
        backref="item_properties",
        lazy=True
    )


    FIELD_TYPES = {
        "text",
        "number",
        "select",
        "check_box",
    }

    @validates("field_type")
    def validate_field_type(self, key, value):
        if value not in self.FIELD_TYPES:
            raise ValueError(
                f"Invalid field_type '{value}'. "
                f"Allowed values: {self.FIELD_TYPES}"
            )
        current_options = getattr(self, "options", None)
        normalized_options = self._normalize_options(value, current_options)
        if normalized_options is not current_options:
            self.options = normalized_options
        return value

    @validates("options")
    def validate_options(self, key, value):
        return self._normalize_options(getattr(self, "field_type", None), value)

    @staticmethod
    def _normalize_options(field_type, options):
        if options is None:
            return None

        if field_type != "select":
            return options

        if isinstance(options, list):
            if not all(isinstance(item, str) and item.strip() for item in options):
                raise ValueError("For select field_type, options must be a list of non-empty strings.")
            return options

        # Backward compatibility for legacy payload shape: {"values": [...]}.
        if isinstance(options, dict):
            values = options.get("values")
            if isinstance(values, list) and all(
                isinstance(item, str) and item.strip() for item in values
            ):
                return values

        raise ValueError(
            "For select field_type, options must be a list of non-empty strings."
        )