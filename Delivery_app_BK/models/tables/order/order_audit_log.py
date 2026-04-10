from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, ForeignKey, JSON

from datetime import datetime, timezone

# Local application imports
from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.utils import UTCDateTime


class OrderAuditLog(db.Model, TeamScopedMixin):
    __tablename__ = "order_audit_log"

    id = Column( Integer, primary_key=True )
    client_id = Column(String, index=True)

    field_name = Column(String, nullable=False, index=True)

    from_value = Column(JSONB().with_variant(JSON, "sqlite"))
    to_value = Column(JSONB().with_variant(JSON, "sqlite"))

    user_name = Column(String)

    changed_at = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc), index=True)
    changed_by_user_id = Column(
        Integer,
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )
    order_id = Column(
        Integer,
        ForeignKey("order.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    order = relationship(
        "Order",
        backref="audit_logs",
        lazy="selectin",
    )
    changed_by_user = relationship(
        "User",
        lazy="selectin",
    )
