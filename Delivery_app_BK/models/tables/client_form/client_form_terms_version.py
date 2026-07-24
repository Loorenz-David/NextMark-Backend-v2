from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, validates

from Delivery_app_BK.models import db
from Delivery_app_BK.models.utils import UTCDateTime
from Delivery_app_BK.services.domain.client_form.terms import validate_terms_content


class ClientFormTermsVersion(db.Model):
    """Immutable terms-and-conditions version scoped to a team.

    Rows are never updated or deleted — publishing appends a new row and clears
    the previous active flag. Orders reference the row they were accepted under,
    so the exact accepted text stays recoverable.
    """

    __tablename__ = "client_form_terms_version"

    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "version_number",
            name="uq_client_form_terms_version_team_version",
        ),
        Index(
            "uix_client_form_terms_active_team",
            "team_id",
            unique=True,
            postgresql_where=text("is_active IS TRUE"),
        ),
        Index("ix_client_form_terms_team_created", "team_id", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    team_id = Column(
        Integer,
        ForeignKey("team.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number = Column(Integer, nullable=False)
    content = Column(JSONB().with_variant(JSON, "sqlite"), nullable=False)
    is_active = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        UTCDateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    created_by_user_id = Column(
        Integer,
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )

    team = relationship("Team", backref="client_form_terms_versions", lazy=True)

    @validates("content")
    def validate_content(self, key, value):
        return validate_terms_content(value)
