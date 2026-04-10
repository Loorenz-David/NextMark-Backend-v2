from sqlalchemy.orm import validates
from sqlalchemy import Column, Integer, String,  Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship

from Delivery_app_BK.errors import ValidationFailed
from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.utils import UTCDateTime
from Delivery_app_BK.services.domain.messaging import (
    ALLOWED_SCHEDULE_OFFSET_UNITS,
    validate_schedule_configuration,
)
from Delivery_app_BK.services.domain.order.order_events import OrderEvent
from Delivery_app_BK.services.domain.route_operations.plan.plan_events import RoutePlanEvent

class MessageTemplate(db.Model, TeamScopedMixin):
    __tablename__ = "message_template"
    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "event",
            "channel",
            name="uq_message_template_team_event_channel"
        ),
    )

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)
    event = Column(String)
    enable = Column(Boolean)
    template = Column(JSONB)
    name = Column(String)
    ask_permission = Column(Boolean, default=False)
    channel = Column(String, nullable=False)
    schedule_offset_value = Column(Integer, nullable=True)
    schedule_offset_unit = Column(String, nullable=True)


    timestampt = Column(UTCDateTime)

    team = relationship(
        "Team",
        backref="message_templates",
        lazy=True
    )


    ALLOWED_CHANNELS = set(["sms", "email", "whatsapp","telegram"])
    @validates("channel")
    def validate_channel(self, key, value):
        if value not in self.ALLOWED_CHANNELS:
            raise ValidationFailed(
                f"Invalid channel '{value}'. "
                f"Allowed values: {self.ALLOWED_CHANNELS}"
            )
        return value
    

    @validates("event")
    def validate_event(self, key, value):
        if (value not in OrderEvent._value2member_map_ and value not in RoutePlanEvent._value2member_map_):
            raise ValidationFailed(
                f"Invalid event '{value}'. "
                f"Allowed events: {[e.value for e in OrderEvent]}"
            )
        self._validate_schedule_configuration(event_name=value)
        return value

    @validates("schedule_offset_value")
    def validate_schedule_offset_value(self, key, value):
        self._validate_schedule_configuration(offset_value=value)
        return value

    @validates("schedule_offset_unit")
    def validate_schedule_offset_unit(self, key, value):
        if value is not None and value not in ALLOWED_SCHEDULE_OFFSET_UNITS:
            raise ValidationFailed(
                f"Invalid schedule_offset_unit '{value}'. "
                f"Allowed values: {sorted(ALLOWED_SCHEDULE_OFFSET_UNITS)}"
            )
        self._validate_schedule_configuration(offset_unit=value)
        return value

    def _validate_schedule_configuration(
        self,
        *,
        event_name=None,
        offset_value=None,
        offset_unit=None,
    ) -> None:
        current_event_name = self.event if event_name is None else event_name
        current_offset_value = self.schedule_offset_value if offset_value is None else offset_value
        current_offset_unit = self.schedule_offset_unit if offset_unit is None else offset_unit
        if current_offset_value is None or current_offset_unit is None:
            return

        validate_schedule_configuration(
            event_name=current_event_name,
            offset_value=current_offset_value,
            offset_unit=current_offset_unit,
        )


class SafeDict(dict):
    def __missing__(self, key):
        # Return the placeholder unchanged if missing
        return f"{{{key}}}"
