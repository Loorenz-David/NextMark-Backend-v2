from sqlalchemy import  ForeignKey, Integer, Column
from sqlalchemy.orm import relationship


class TeamScopedMixin:
    team_id = Column(Integer, ForeignKey("team.id"))
    
