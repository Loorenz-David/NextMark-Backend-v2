# Third-party dependencies
import re
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship, validates

# Local application imports
from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.utils import UTCDateTime


HH_MM_PATTERN = re.compile(r"^\d{2}:\d{2}$")


class CostumerOperatingHours(db.Model, TeamScopedMixin):
    __tablename__ = "costumer_operating_hours"

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True, nullable=True)
    costumer_id = Column(
        Integer,
        ForeignKey("costumer.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    weekday = Column(Integer, nullable=False)
    open_time = Column(String(5), nullable=False)
    close_time = Column(String(5), nullable=False)
    is_closed = Column(Boolean, default=False)
    created_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc))

    costumer = relationship(
        "Costumer",
        back_populates="operating_hours",
        foreign_keys=[costumer_id],
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("costumer_id", "weekday", name="uq_costumer_operating_hours_weekday"),
    )

    @validates("weekday")
    def validate_weekday(self, key, value):
        if value is None:
            raise ValueError("weekday is required")
        if value < 0 or value > 6:
            raise ValueError("weekday must be between 0 and 6")
        return value

    @validates("open_time", "close_time")
    def validate_hh_mm(self, key, value):
        if value is None:
            raise ValueError(f"{key} is required")
        if not HH_MM_PATTERN.match(value):
            raise ValueError(f"{key} must be formatted as HH:MM")

        hour = int(value[0:2])
        minute = int(value[3:5])
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError(f"{key} must be a valid time in HH:MM")

        return value
