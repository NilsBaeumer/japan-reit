import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)

    # Location
    municipality_code: Mapped[str | None] = mapped_column(
        String(5), ForeignKey("municipalities.code"), nullable=True, index=True
    )
    address_ja: Mapped[str] = mapped_column(Text)
    address_normalized: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Core attributes
    property_type: Mapped[str] = mapped_column(String(30), default="detached_house")
    price: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    land_area_sqm: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    building_area_sqm: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    floor_plan: Mapped[str | None] = mapped_column(String(20), nullable=True)
    year_built: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    structure: Mapped[str | None] = mapped_column(String(30), nullable=True)
    floors: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # Road / rebuild status
    road_width_m: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)
    road_frontage_m: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)
    setback_required: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    rebuild_possible: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Zoning
    city_planning_zone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    use_zone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    coverage_ratio: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    floor_area_ratio: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    # Scoring
    composite_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    score_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Status tracking
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    # Relationships
    listings: Mapped[list["PropertyListing"]] = relationship(
        back_populates="property", cascade="all, delete-orphan"
    )
    images: Mapped[list["PropertyImage"]] = relationship(
        back_populates="property", cascade="all, delete-orphan"
    )


class PropertyListing(Base):
    __tablename__ = "property_listings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    property_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("properties.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(30))
    source_url: Mapped[str] = mapped_column(Text)
    source_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Source-specific raw data
    raw_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    raw_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Listing lifecycle
    listing_status: Mapped[str] = mapped_column(String(20), default="active")
    first_scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    delisted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    property: Mapped["Property"] = relationship(back_populates="listings")

    __table_args__ = (
        Index("uq_listings_source_id", source, source_id, unique=True),
    )


class PropertyImage(Base):
    __tablename__ = "property_images"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    property_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("properties.id", ondelete="CASCADE"), index=True
    )
    listing_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("property_listings.id"), nullable=True
    )
    url: Mapped[str] = mapped_column(Text)
    local_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    property: Mapped["Property"] = relationship(back_populates="images")
