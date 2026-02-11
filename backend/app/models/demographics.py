import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


class PopulationMesh(Base):
    __tablename__ = "population_mesh"

    mesh_code: Mapped[str] = mapped_column(String(12), primary_key=True)
    # Bounding box replacing Geometry("POLYGON")
    bbox_min_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_min_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_max_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_max_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    municipality_code: Mapped[str | None] = mapped_column(
        String(5), ForeignKey("municipalities.code"), nullable=True, index=True
    )

    # From reinfolib XKT013 (500m mesh population projections)
    population_current: Mapped[int | None] = mapped_column(Integer, nullable=True)
    population_2030: Mapped[int | None] = mapped_column(Integer, nullable=True)
    population_2040: Mapped[int | None] = mapped_column(Integer, nullable=True)
    population_2050: Mapped[int | None] = mapped_column(Integer, nullable=True)
    households_current: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elderly_ratio: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class TransactionHistory(Base):
    __tablename__ = "transaction_history"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid_str
    )

    # From reinfolib XIT001
    municipality_code: Mapped[str | None] = mapped_column(
        String(5), index=True, nullable=True
    )
    district_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Replacing Geometry("POINT") with simple lat/lng
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    property_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    trade_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    price_per_sqm: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    area_sqm: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    building_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    structure: Mapped[str | None] = mapped_column(String(30), nullable=True)
    trade_quarter: Mapped[str | None] = mapped_column(String(10), nullable=True)

    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
