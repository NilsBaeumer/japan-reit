import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


class HazardAssessment(Base):
    __tablename__ = "hazard_assessments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid_str
    )
    property_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("properties.id", ondelete="CASCADE"), unique=True
    )

    # Seismic (from J-SHIS)
    seismic_intensity_prob: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    pga_475yr: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    liquefaction_risk: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Flood (from Hazard Map Portal / reinfolib XKT016)
    flood_depth_max_m: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)
    flood_zone: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Tsunami
    tsunami_risk: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tsunami_depth_max_m: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)

    # Landslide (from J-SHIS landslide API + XKT021/XKT022)
    landslide_risk: Mapped[str | None] = mapped_column(String(20), nullable=True)
    steep_slope_zone: Mapped[bool] = mapped_column(Boolean, default=False)
    landslide_prevention_zone: Mapped[bool] = mapped_column(Boolean, default=False)

    # Metadata
    mesh_code: Mapped[str | None] = mapped_column(String(12), nullable=True)
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    data_sources: Mapped[dict | None] = mapped_column(JSON, nullable=True)
