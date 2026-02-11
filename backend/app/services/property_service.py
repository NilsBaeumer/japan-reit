"""Property service - handles creation, updating, and deduplication of properties."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.property import Property, PropertyListing, PropertyImage
from app.scrapers.base import RawListing
from app.services.dedup_service import DeduplicationService
from app.utils.japanese_address import normalize_address


class PropertyService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.dedup = DeduplicationService(session)

    async def upsert_from_listing(self, raw: RawListing) -> bool:
        """
        Create or update a property from a raw listing.

        Returns True if this is a new property, False if existing.
        """
        # Check if we already have this listing by source + source_id
        existing_listing = await self._find_existing_listing(raw.source, raw.source_id)

        if existing_listing:
            # Update existing listing
            existing_listing.raw_price = raw.price
            existing_listing.raw_title = raw.title
            existing_listing.raw_data = raw.raw_data
            existing_listing.last_scraped_at = datetime.now(timezone.utc)
            existing_listing.listing_status = "active"

            # Update parent property
            prop = await self.session.get(Property, existing_listing.property_id)
            if prop:
                self._update_property_from_raw(prop, raw)
                prop.last_seen_at = datetime.now(timezone.utc)

            return False

        # Try to find matching property via deduplication (address, fuzzy, spatial)
        prop = await self.dedup.find_matching_property(raw)

        if prop is None:
            # Create new property
            prop = Property(
                address_ja=raw.address or "Unknown",
                address_normalized=normalize_address(raw.address or ""),
                property_type=raw.raw_data.get("property_type", "detached_house"),
                status="active",
            )
            self._update_property_from_raw(prop, raw)
            self.session.add(prop)
            await self.session.flush()
            is_new = True
        else:
            self._update_property_from_raw(prop, raw)
            prop.last_seen_at = datetime.now(timezone.utc)
            is_new = False

        # Create listing record
        listing = PropertyListing(
            property_id=prop.id,
            source=raw.source,
            source_url=raw.source_url,
            source_id=raw.source_id,
            raw_price=raw.price,
            raw_title=raw.title,
            raw_description=raw.raw_data.get("description"),
            raw_data=raw.raw_data,
        )
        self.session.add(listing)

        # Save images
        for i, url in enumerate(raw.image_urls):
            img = PropertyImage(
                property_id=prop.id,
                url=url,
                image_type="exterior" if i == 0 else "interior",
                sort_order=i,
            )
            self.session.add(img)

        await self.session.flush()
        return is_new

    def _update_property_from_raw(self, prop: Property, raw: RawListing):
        """Update property fields from raw listing data."""
        if raw.price is not None:
            prop.price = raw.price
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
        if raw.road_frontage_m is not None:
            prop.road_frontage_m = raw.road_frontage_m
        if raw.rebuild_possible is not None:
            prop.rebuild_possible = raw.rebuild_possible
        if raw.city_planning_zone:
            prop.city_planning_zone = raw.city_planning_zone
        if raw.use_zone:
            prop.use_zone = raw.use_zone
        if raw.coverage_ratio is not None:
            prop.coverage_ratio = raw.coverage_ratio
        if raw.floor_area_ratio is not None:
            prop.floor_area_ratio = raw.floor_area_ratio
        if raw.latitude is not None and raw.longitude is not None:
            prop.latitude = raw.latitude
            prop.longitude = raw.longitude
        if raw.address:
            prop.address_ja = raw.address
            prop.address_normalized = normalize_address(raw.address)

        prop.updated_at = datetime.now(timezone.utc)

    async def _find_existing_listing(
        self, source: str, source_id: str
    ) -> PropertyListing | None:
        """Find an existing listing by source and source_id."""
        result = await self.session.execute(
            select(PropertyListing).where(
                PropertyListing.source == source,
                PropertyListing.source_id == source_id,
            )
        )
        return result.scalar_one_or_none()

