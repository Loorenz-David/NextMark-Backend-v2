# Third-party dependecies
from datetime import date, datetime, time, timezone

from sqlalchemy import Column, Float, ForeignKey, Index, Integer, String, text, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, validates

# Local application imports
from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.utils import UTCDateTime



class RoutePlan(db.Model, TeamScopedMixin):
    __tablename__ = "route_plan"

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)

    label = Column(String, nullable=False, index=True)
    date_strategy = Column(String, nullable=False, default="single", index=True)

  
    start_date = Column(UTCDateTime, index=True) 
    end_date = Column(UTCDateTime, index=True) 

    created_at = Column(
        UTCDateTime,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        UTCDateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    state_id = Column(Integer, ForeignKey("plan_state.id", ondelete="SET NULL"))

    total_weight_g   = Column(Float, nullable=True)
    total_volume_cm3 = Column(Float, nullable=True)
    total_item_count = Column(Integer, nullable=True)
    total_orders     = Column(Integer, nullable=True)
    item_type_counts = Column(JSONB().with_variant(JSON, "sqlite"), nullable=True)

    state = relationship("RoutePlanState", back_populates="route_plans", lazy="selectin")

    orders = relationship(
        "Order",
        back_populates="route_plan",
    )

    route_groups = relationship(
        "RouteGroup",
        back_populates="route_plan",
        passive_deletes=True,
    )

    events = relationship(
        "RoutePlanEvent",
        back_populates="route_plan",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    DATE_STRATEGIES = {"single", "range"}

    @validates("date_strategy")
    def validate_date_strategy(self, key, value):
        if value not in self.DATE_STRATEGIES:
            raise ValueError(
                f"Invalid date_strategy '{value}'. "
                f"Allowed values: {self.DATE_STRATEGIES}"
            )
        if value == "single" and self.start_date is not None:
            self.end_date = self._normalize_end_of_day(self.start_date)
        return value

    @validates("start_date")
    def validate_start_date(self, key, value):
        normalized = self._normalize_start_of_day(value)
        if getattr(self, "date_strategy", "single") == "single":
            # Write directly to avoid chaining into validate_end_date, which would
            # compare the new end against the still-old self.start_date mid-assignment.
            # The auto-set value is always valid: end-of-day of the incoming start.
            self.__dict__["end_date"] = self._normalize_end_of_day(normalized)
        return normalized

    @validates("end_date")
    def validate_end_date(self, key, value):
        if value is None:
            if getattr(self, "date_strategy", "single") == "single" and self.start_date is not None:
                return self._normalize_end_of_day(self.start_date)
            return None
        normalized = self._normalize_end_of_day(value)
        if self.start_date and normalized < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return normalized

    @staticmethod
    def _coerce_datetime(value):
        if isinstance(value, str):
            parsed = value.strip().replace("Z", "+00:00")
            if len(parsed) == 10 and parsed[4] == "-" and parsed[7] == "-":
                value = datetime.fromisoformat(parsed)
            else:
                value = datetime.fromisoformat(parsed)
        elif isinstance(value, date) and not isinstance(value, datetime):
            value = datetime.combine(value, time.min)

        if not isinstance(value, datetime):
            raise ValueError("Date value must be an ISO datetime string or YYYY-MM-DD")

        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @classmethod
    def _normalize_start_of_day(cls, value):
        if value is None:
            return None
        dt = cls._coerce_datetime(value)
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)

    @classmethod
    def _normalize_end_of_day(cls, value):
        if value is None:
            return None
        dt = cls._coerce_datetime(value)
        return dt.replace(hour=23, minute=59, second=59, microsecond=999999)

    __table_args__ = (
        Index("ix_route_plan_created_at_id_desc", created_at.desc(), id.desc()),
        Index(
            "uq_route_plan_team_client_id",
            "team_id",
            "client_id",
            unique=True,
            postgresql_where=text("client_id IS NOT NULL"),
        ),
    )
