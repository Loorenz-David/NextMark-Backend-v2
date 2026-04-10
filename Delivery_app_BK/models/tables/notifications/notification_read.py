# Third-party dependecies
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Index, text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, Text, String, Boolean, ForeignKey

from datetime import datetime, timezone

# Local application imports
from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.utils import UTCDateTime


class NotificationRead( db.Model ):
    __tablename__ = "notification_read"
    id = Column( Integer, primary_key = True )
    client_id = Column(String, index=True, nullable=True )

    reader_name = Column( String )
    seen_at = Column(
        UTCDateTime,
        default= lambda: datetime.now(timezone.utc),
        nullable = False
    )

    user_id = Column(
        Integer,
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable= True
    )

    case_chat_id = Column(
        Integer,
        ForeignKey("case_chat.id", ondelete="CASCADE")
    )

    case_chat = relationship(
        "CaseChat",
        back_populates = "notification_reads"
    )
