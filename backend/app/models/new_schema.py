"""SQLAlchemy models matching the Next.js Drizzle schema exactly.

These models map 1:1 to the tables created by the Next.js app via Drizzle ORM.
The scraper writes to these tables; the Next.js app reads from them.

Key differences from old models:
- Serial integer PKs (not UUIDs)
- Column names match Drizzle schema (e.g. price_jpy not price, lat/lng not latitude/longitude)
- property_images uses storage_path (Supabase Storage) not url
- property_listings uses source_id (FK to listing_sources) and source_listing_id
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class NewProperty(Base):
    """Maps to Drizzle 'properties' table (serial PK)."""

    __tablename__ = "properties"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Location
    address_ja: Mapped[str] = mapped_column(Text, nullable=False)
    address_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    prefecture_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    municipality_code: Mapped[str | None] = mapped_column(String(5), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Physical
    price_jpy: Mapped[int] = mapped_column(Integer, nullable=False)
    land_area_sqm: Mapped[float | None] = mapped_column(Float, nullable=True)
    building_area_sqm: Mapped[float | None] = mapped_column(Float, nullable=True)
    floor_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    year_built: Mapped[int | None] = mapped_column(Integer, nullable=True)
    structure: Mapped[str | None] = mapped_column(Text, nullable=True)
    floors: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Legal
    land_rights: Mapped[str | None] = mapped_column(Text, nullable=True)
    road_width_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    rebuild_possible: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Zoning
    use_zone: Mapped[str | None] = mapped_column(Text, nullable=True)
    coverage_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    floor_area_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Computed
    composite_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_per_sqm: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Text content
    description_ja: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    area_info_en: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metadata
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )


class NewPropertyListing(Base):
    """Maps to Drizzle 'property_listings' table."""

    __tablename__ = "property_listings"
    __table_args__ = (
        UniqueConstraint("source_id", "source_listing_id", name="uq_property_listings_source"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    property_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[str] = mapped_column(Text, nullable=False)  # FK to listing_sources
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_listing_id: Mapped[str] = mapped_column(Text, nullable=False)
    raw_data_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    listing_status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    first_scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    last_scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    delisted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class NewPropertyImage(Base):
    """Maps to Drizzle 'property_images' table."""

    __tablename__ = "property_images"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    property_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False
    )
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    alt_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class NewHazardAssessment(Base):
    """Maps to Drizzle 'hazard_assessments' table."""

    __tablename__ = "hazard_assessments"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    property_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    seismic_intensity: Mapped[str | None] = mapped_column(Text, nullable=True)
    pga_475yr: Mapped[float | None] = mapped_column(Float, nullable=True)
    liquefaction_risk: Mapped[str | None] = mapped_column(Text, nullable=True)
    flood_depth_max_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    flood_zone: Mapped[str | None] = mapped_column(Text, nullable=True)
    tsunami_risk: Mapped[str | None] = mapped_column(Text, nullable=True)
    tsunami_depth_max_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    landslide_risk: Mapped[str | None] = mapped_column(Text, nullable=True)
    landslide_zone: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_sources_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )


class NewPropertyScore(Base):
    """Maps to Drizzle 'property_scores' table."""

    __tablename__ = "property_scores"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    property_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    rebuild_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    hazard_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    infrastructure_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    demographic_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    value_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    condition_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    weights_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    composite_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    scoring_version: Mapped[str] = mapped_column(Text, nullable=False, default="1.0")
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
