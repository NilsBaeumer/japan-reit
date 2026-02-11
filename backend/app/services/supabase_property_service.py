"""Property service for the new Drizzle-compatible schema.

Writes scraped data to the Supabase PostgreSQL tables that the Next.js app reads.
Handles deduplication by source + source_listing_id unique constraint.
"""

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.new_schema import NewProperty, NewPropertyListing, NewPropertyImage
from app.scrapers.base import RawListing
from app.services.translate_service import TranslateService
from app.services.image_upload_service import ImageUploadService
from app.utils.japanese_address import normalize_address

import structlog

logger = structlog.get_logger()


class SupabasePropertyService:
    """Saves scraped properties to the Drizzle-compatible schema."""

    def __init__(
        self,
        session: AsyncSession,
        translate_service: TranslateService | None = None,
        image_service: ImageUploadService | None = None,
    ):
        self.session = session
        self.translate = translate_service
        self.images = image_service

    async def upsert_from_listing(self, raw: RawListing) -> bool:
        """Create or update a property from a scraped listing.

        Returns True if new property created, False if existing updated.
        """
        # Check for existing listing by source + source_listing_id
        existing = await self._find_existing_listing(raw.source, raw.source_id)

        if existing:
            # Update existing listing
            existing.raw_data_json = raw.raw_data
            existing.last_scraped_at = datetime.now(timezone.utc)
            existing.listing_status = "active"

            # Update parent property
            prop = await self.session.get(NewProperty, existing.property_id)
            if prop:
                self._update_property_fields(prop, raw)

            return False

        # Try to find matching property by address
        prop = await self._find_by_address(raw.address or "")

        if prop is None:
            # Create new property
            prop = NewProperty(
                address_ja=raw.address or "Unknown",
                price_jpy=raw.price or 0,
                status="active",
            )
            self._update_property_fields(prop, raw)

            # Translate description if service available
            if self.translate and raw.raw_data.get("description"):
                try:
                    prop.description_ja = raw.raw_data["description"]
                    prop.description_en = await self.translate.translate(
                        raw.raw_data["description"]
                    )
                except Exception as e:
                    logger.warning("Translation failed", error=str(e))

            self.session.add(prop)
            await self.session.flush()  # Get the serial ID
            is_new = True
        else:
            self._update_property_fields(prop, raw)
            is_new = False

        # Compute price_per_sqm
        if prop.price_jpy and prop.land_area_sqm and prop.land_area_sqm > 0:
            prop.price_per_sqm = prop.price_jpy / prop.land_area_sqm

        # Create listing record
        listing = NewPropertyListing(
            property_id=prop.id,
            source_id=raw.source,
            source_url=raw.source_url,
            source_listing_id=raw.source_id,
            raw_data_json=raw.raw_data,
        )
        self.session.add(listing)

        # Upload images and save records
        for i, url in enumerate(raw.image_urls):
            storage_path = url  # Default: store the remote URL
            if self.images:
                try:
                    uploaded_path = await self.images.upload_from_url(
                        url, property_id=prop.id, index=i
                    )
                    if uploaded_path:
                        storage_path = uploaded_path
                except Exception as e:
                    logger.warning("Image upload failed", url=url, error=str(e))

            img = NewPropertyImage(
                property_id=prop.id,
                storage_path=storage_path,
                sort_order=i,
                alt_text=f"Property image {i + 1}",
            )
            self.session.add(img)

        await self.session.flush()
        return is_new

    def _update_property_fields(self, prop: NewProperty, raw: RawListing):
        """Update property fields from raw listing data."""
        if raw.price is not None:
            prop.price_jpy = raw.price
        if raw.land_area_sqm is not None:
            prop.land_area_sqm = raw.land_area_sqm
        if raw.building_area_sqm is not None:
            prop.building_area_sqm = raw.building_area_sqm
        if raw.floor_plan:
            prop.floor_plan = raw.floor_plan
        if raw.year_built is not None:
            prop.year_built = raw.year_built
        if raw.structure:
            prop.structure = raw.structure
        if raw.floors is not None:
            prop.floors = raw.floors
        if raw.road_width_m is not None:
            prop.road_width_m = raw.road_width_m
        if raw.rebuild_possible is not None:
            prop.rebuild_possible = raw.rebuild_possible
        if raw.use_zone:
            prop.use_zone = raw.use_zone
        if raw.coverage_ratio is not None:
            prop.coverage_ratio = raw.coverage_ratio
        if raw.floor_area_ratio is not None:
            prop.floor_area_ratio = raw.floor_area_ratio
        if raw.latitude is not None and raw.longitude is not None:
            prop.lat = raw.latitude
            prop.lng = raw.longitude
        if raw.address:
            prop.address_ja = raw.address
        if raw.municipality:
            prop.municipality_code = raw.municipality
        if raw.prefecture:
            prop.prefecture_code = raw.prefecture

        prop.updated_at = datetime.now(timezone.utc)

    async def _find_existing_listing(
        self, source: str, source_listing_id: str
    ) -> NewPropertyListing | None:
        """Find an existing listing by source + source_listing_id."""
        result = await self.session.execute(
            select(NewPropertyListing).where(
                NewPropertyListing.source_id == source,
                NewPropertyListing.source_listing_id == source_listing_id,
            )
        )
        return result.scalar_one_or_none()

    async def _find_by_address(self, address: str) -> NewProperty | None:
        """Find an existing property by exact address match."""
        if not address or address == "Unknown":
            return None
        result = await self.session.execute(
            select(NewProperty).where(NewProperty.address_ja == address).limit(1)
        )
        return result.scalar_one_or_none()
