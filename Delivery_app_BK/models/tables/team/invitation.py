# Thirs-party dependencies
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, ForeignKey
from datetime import datetime, timezone

# Local application imports
from Delivery_app_BK.models import db
from Delivery_app_BK.models.mixins.team_mixings.team_id import TeamScopedMixin
from Delivery_app_BK.models.utils import UTCDateTime


class TeamInvites(db.Model, TeamScopedMixin):
    __tablename__ = "team_invites"

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)

    from_team_name = Column(String, nullable=False)
    target_username = Column(String, nullable=False)
    target_email = Column(String, nullable=False)

    user_role_name = Column( String, nullable=False )
    user_role_id = Column( Integer, nullable=False )

    creation_date = Column(UTCDateTime, default=lambda: datetime.now(timezone.utc))

    target_user_id = Column(
        Integer, 
        ForeignKey("user.id"), 
        nullable=True
    )

    team = relationship("Team", lazy=True)
    user = relationship("User", lazy=True)
