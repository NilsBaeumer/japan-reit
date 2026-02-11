"""Deduplication service for matching properties across multiple listing sources."""

import math
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.property import Property
from app.scrapers.base import RawListing
from app.utils.japanese_address import normalize_address

# Thresholds
ADDRESS_SIMILARITY_THRESHOLD = 0.85
SPATIAL_MATCH_DISTANCE_M = 50.0
EARTH_RADIUS_M = 6_371_000


class DeduplicationService:
    """Finds duplicate properties across multiple listing sources."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_matching_property(self, raw: RawListing) -> Property | None:
        """
        Find an existing property that matches the raw listing.

        Matching tiers (in order of confidence):
        1. Exact normalized address match
        2. Fuzzy address match within same municipality
        3. Spatial proximity match (lat/lng within 50m)
        """
        normalized = normalize_address(raw.address or "")

        # Tier 1: Exact normalized address
        if normalized:
            prop = await self._exact_address_match(normalized)
            if prop:
                return prop

        # Tier 2: Fuzzy address match within municipality
        if normalized and raw.municipality:
            prop = await self._fuzzy_address_match(normalized, raw.municipality)
            if prop:
                return prop

        # Tier 3: Spatial proximity
        if raw.latitude is not None and raw.longitude is not None:
            prop = await self._spatial_match(raw.latitude, raw.longitude)
            if prop:
                return prop

        return None

    async def _exact_address_match(self, normalized_address: str) -> Property | None:
        """Find property with exact normalized address match."""
        result = await self.session.execute(
            select(Property)
            .where(Property.address_normalized == normalized_address)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _fuzzy_address_match(
        self, normalized_address: str, municipality: str
    ) -> Property | None:
        """Find property with similar address in same municipality."""
        # Get candidate properties in same municipality
        result = await self.session.execute(
            select(Property)
            .where(
                Property.address_normalized.isnot(None),
                Property.address_ja.contains(municipality),
            )
            .limit(100)
        )
        candidates = result.scalars().all()

        best_match: Property | None = None
        best_score = 0.0

        for candidate in candidates:
            if candidate.address_normalized:
                score = self.calculate_address_similarity(
                    normalized_address, candidate.address_normalized
                )
                if score > best_score and score >= ADDRESS_SIMILARITY_THRESHOLD:
                    best_score = score
                    best_match = candidate

        return best_match

    async def _spatial_match(self, lat: float, lng: float) -> Property | None:
        """Find property within spatial proximity threshold."""
        # Rough bounding box filter first (approx 0.0005 degrees ~ 50m)
        delta = 0.0005
        result = await self.session.execute(
            select(Property).where(
                Property.latitude.isnot(None),
                Property.longitude.isnot(None),
                Property.latitude.between(lat - delta, lat + delta),
                Property.longitude.between(lng - delta, lng + delta),
            )
        )
        candidates = result.scalars().all()

        for candidate in candidates:
            if candidate.latitude and candidate.longitude:
                dist = self.calculate_distance_m(
                    lat, lng, candidate.latitude, candidate.longitude
                )
                if dist <= SPATIAL_MATCH_DISTANCE_M:
                    return candidate

        return None

    @staticmethod
    def calculate_address_similarity(addr1: str, addr2: str) -> float:
        """
        Calculate similarity between two normalized addresses.
        Uses character-level comparison optimized for Japanese addresses.
        Returns a score between 0.0 and 1.0.
        """
        if addr1 == addr2:
            return 1.0
        if not addr1 or not addr2:
            return 0.0

        # Simple Jaccard similarity on character bigrams
        def bigrams(s: str) -> set[str]:
            return {s[i : i + 2] for i in range(len(s) - 1)} if len(s) >= 2 else {s}

        bg1 = bigrams(addr1)
        bg2 = bigrams(addr2)

        intersection = len(bg1 & bg2)
        union = len(bg1 | bg2)

        return intersection / union if union > 0 else 0.0

    @staticmethod
    def calculate_distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate distance in meters between two points using Haversine formula."""
        lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlng / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))
        return EARTH_RADIUS_M * c
