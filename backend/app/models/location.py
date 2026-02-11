from datetime import datetime, timezone

from sqlalchemy import Float, ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Prefecture(Base):
    __tablename__ = "prefectures"

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name_ja: Mapped[str] = mapped_column(String(10))
    name_en: Mapped[str] = mapped_column(String(50))
    region: Mapped[str] = mapped_column(String(20))

    municipalities: Mapped[list["Municipality"]] = relationship(back_populates="prefecture")


class Municipality(Base):
    __tablename__ = "municipalities"

    code: Mapped[str] = mapped_column(String(5), primary_key=True)
    prefecture_code: Mapped[str] = mapped_column(
        String(2), ForeignKey("prefectures.code"), index=True
    )
    name_ja: Mapped[str] = mapped_column(String(50))
    name_en: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Bounding box replacing Geometry("MULTIPOLYGON")
    bbox_min_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_min_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_max_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_max_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    population: Mapped[int | None] = mapped_column(Integer, nullable=True)
    households: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    prefecture: Mapped["Prefecture"] = relationship(back_populates="municipalities")
