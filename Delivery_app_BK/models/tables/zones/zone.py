from datetime import datetime, timezone
import json
import re

from sqlalchemy import Boolean, Column, Enum, Float, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import JSON
from sqlalchemy.orm import relationship, validates
from geoalchemy2 import Geometry
from geoalchemy2.elements import WKBElement
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import MultiPolygon, mapping, shape

from Delivery_app_BK.models import db
from Delivery_app_BK.models.utils import UTCDateTime


class Zone(db.Model):
    """Versioned spatial zone shared across analytics and other domains."""

    __tablename__ = "zone"

    __table_args__ = (
        Index("ix_zone_team_version_active", "team_id", "zone_version_id", "is_active"),
        Index("ix_zone_team_city_version", "team_id", "city_key", "zone_version_id"),
        Index(
            "ix_zone_bbox_lookup",
            "team_id",
            "city_key",
            "zone_version_id",
            "min_lat",
            "max_lat",
            "min_lng",
            "max_lng",
        ),
    )

    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, db.ForeignKey("team.id", ondelete="CASCADE"), nullable=False, index=True)
    zone_version_id = Column(
        Integer,
        db.ForeignKey("zone_version.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    city_key = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    zone_color = Column(String(7), nullable=True)
    zone_type = Column(
        Enum("bootstrap", "system", "user", name="zone_type_enum"),
        nullable=False,
    )
    centroid_lat = Column(Float, nullable=True)
    centroid_lng = Column(Float, nullable=True)
    geom_high_res = Column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=False).with_variant(JSON(), "sqlite"),
        nullable=True,
    )
    geom_simplified = Column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=False).with_variant(JSON(), "sqlite"),
        nullable=True,
    )
    min_lat = Column(Float, nullable=True)
    max_lat = Column(Float, nullable=True)
    min_lng = Column(Float, nullable=True)
    max_lng = Column(Float, nullable=True)
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

    templates = relationship(
        "ZoneTemplate",
        back_populates="zone",
        cascade="all, delete-orphan",
    )

    @staticmethod
    def _is_sqlite_backend() -> bool:
        try:
            bind = db.session.get_bind()
        except Exception:
            return False
        if bind is None:
            return False
        return bind.dialect.name == "sqlite"

    @staticmethod
    def _normalize_geojson(value):
        if value is None:
            return None
        if isinstance(value, str):
            return json.loads(value)
        return value

    @classmethod
    def _encode_geometry(cls, value):
        geojson = cls._normalize_geojson(value)
        if geojson is None:
            return None
        if cls._is_sqlite_backend():
            return geojson

        geom = shape(geojson)
        if geom.geom_type == "Polygon":
            geom = MultiPolygon([geom])
        return from_shape(geom, srid=4326)

    @classmethod
    def _decode_geometry(cls, value):
        if value is None:
            return None
        if cls._is_sqlite_backend():
            return cls._normalize_geojson(value)
        if isinstance(value, WKBElement):
            return mapping(to_shape(value))
        return cls._normalize_geojson(value)

    @property
    def geometry(self):
        return self._decode_geometry(self.geom_high_res)

    @geometry.setter
    def geometry(self, value):
        self.geom_high_res = self._encode_geometry(value)

    @property
    def geometry_simplified(self):
        return self._decode_geometry(self.geom_simplified)

    @geometry_simplified.setter
    def geometry_simplified(self, value):
        self.geom_simplified = self._encode_geometry(value)

    @validates("zone_color")
    def validate_zone_color(self, key, value):
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("zone_color must be a string.")
        normalized = value.strip()
        if not normalized:
            return None
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", normalized):
            raise ValueError("zone_color must be a valid hex color like #A1B2C3.")
        return normalized
