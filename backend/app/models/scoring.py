import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


class PropertyScore(Base):
    __tablename__ = "property_scores"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid_str
    )
    property_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("properties.id", ondelete="CASCADE"), index=True
    )

    # Individual dimension scores (0-100)
    rebuild_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    hazard_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    infrastructure_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    demographic_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    value_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    condition_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    # Weights used (stored for reproducibility)
    weights: Mapped[dict] = mapped_column(JSON)
    composite_score: Mapped[float] = mapped_column(Numeric(5, 2))

    # Metadata
    scoring_version: Mapped[str] = mapped_column(String(10))
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("uq_property_score_version", property_id, scoring_version, unique=True),
    )
