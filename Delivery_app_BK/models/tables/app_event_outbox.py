from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Integer, JSON, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.events.dispatch_state import DispatchStateMixin
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.utils import UTCDateTime


class AppEventOutbox(db.Model, TeamScopedMixin, DispatchStateMixin):
    __tablename__ = "app_event_outbox"

    id = Column(Integer, primary_key=True)
    event_name = Column(String, nullable=False, index=True)
    payload = Column(JSONB().with_variant(JSON, "sqlite"), nullable=False, default=dict)
    occurred_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    actor_id = Column(
        Integer,
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )

    actor = relationship("User", lazy="selectin")
    team = relationship("Team", backref="app_event_outbox_rows", lazy=True)
