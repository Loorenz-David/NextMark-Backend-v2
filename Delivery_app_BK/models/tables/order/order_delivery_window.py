# Third-party dependencies
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship, validates

# Local application imports
from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.utils import UTCDateTime


class OrderDeliveryWindow(db.Model, TeamScopedMixin):
    __tablename__ = "order_delivery_window"

    WINDOW_TYPES = {
        "EXACT_DATETIME",
        "DATE_ONLY",
        "TIME_RANGE",
        "DATE_RANGE",
        "FULL_RANGE",
    }

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True, nullable=True)
    order_id = Column(
        Integer,
        ForeignKey("order.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_at = Column(UTCDateTime, nullable=False, index=True)
    end_at = Column(UTCDateTime, nullable=False, index=True)
    window_type = Column(String, nullable=False)
    created_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="ck_order_delivery_window_end_after_start"),
        Index("ix_order_delivery_window_order_id_start_at", "order_id", "start_at"),
    )

    order = relationship(
        "Order",
        back_populates="delivery_windows",
        lazy="selectin",
    )

    @validates("window_type")
    def validate_window_type(self, key, value):
        if value not in self.WINDOW_TYPES:
            raise ValueError(
                f"Invalid window_type '{value}'. Allowed values: {self.WINDOW_TYPES}",
            )
        return value

    @validates("start_at")
    def validate_start_at(self, key, value):
        self._validate_aware_datetime("start_at", value)
        end_at = getattr(self, "end_at", None)
        if end_at is not None and end_at <= value:
            raise ValueError("end_at must be greater than start_at")
        return value

    @validates("end_at")
    def validate_end_at(self, key, value):
        self._validate_aware_datetime("end_at", value)
        start_at = getattr(self, "start_at", None)
        if start_at is not None and value <= start_at:
            raise ValueError("end_at must be greater than start_at")
        return value

    @staticmethod
    def _validate_aware_datetime(field_name, value):
        if value is None:
            raise ValueError(f"{field_name} is required")
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError(f"{field_name} must be timezone-aware")
