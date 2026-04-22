from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship

from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.utils import UTCDateTime


class OrderScheduleTarget(db.Model, TeamScopedMixin):
    __tablename__ = "order_schedule_targets"

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)
    name = Column(String, nullable=False)
    endpoint_url = Column(String, nullable=False)
    api_key = Column(String, nullable=False)
    external_shop_id = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
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

    team = relationship(
        "Team",
        backref="order_schedule_targets",
        lazy=True,
    )
