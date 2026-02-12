"""Geocoding service for converting Japanese addresses to coordinates."""

import asyncio
from functools import lru_cache

import structlog
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.property import Property

logger = structlog.get_logger()

# Rate limit: 1 request per second for Nominatim
GEOCODE_DELAY_SECONDS = 1.1


class GeocodingService:
    """Geocode Japanese addresses using Nominatim (OpenStreetMap)."""

    def __init__(self):
        self.geocoder = Nominatim(
            user_agent="japan-reit-tool/0.1",
            timeout=10,
        )
        self._cache: dict[str, tuple[float, float] | None] = {}

    async def geocode_address(self, address: str) -> tuple[float, float] | None:
        """
        Geocode a single Japanese address.

        Returns (latitude, longitude) or None if geocoding failed.
        """
        if not address:
            return None

        # Check cache
        if address in self._cache:
            return self._cache[address]

        try:
            # Run sync geocoder in thread pool
            location = await asyncio.to_thread(
                self.geocoder.geocode,
                address,
                language="ja",
                country_codes="jp",
            )

            if location:
                result = (location.latitude, location.longitude)
                self._cache[address] = result
                logger.info(
                    "Geocoded address",
                    address=address[:50],
                    lat=location.latitude,
                    lng=location.longitude,
                )
                return result
            else:
                # Try with simplified address (remove building names, etc.)
                simplified = self._simplify_address(address)
                if simplified != address:
                    location = await asyncio.to_thread(
                        self.geocoder.geocode,
                        simplified,
                        language="ja",
                        country_codes="jp",
                    )
                    if location:
                        result = (location.latitude, location.longitude)
                        self._cache[address] = result
                        return result

                self._cache[address] = None
                logger.warning("Geocoding returned no results", address=address[:50])
                return None

        except (GeocoderTimedOut, GeocoderServiceError) as e:
            logger.warning("Geocoding error", address=address[:50], error=str(e))
            return None
        except Exception as e:
            logger.error("Unexpected geocoding error", address=address[:50], error=str(e))
            return None

    async def geocode_properties_batch(
        self, session: AsyncSession, limit: int = 100
    ) -> dict[str, int]:
        """
        Geocode properties that don't have coordinates yet.

        Returns stats dict with counts of success/failure/skipped.
        """
        # Find properties without coordinates
        result = await session.execute(
            select(Property)
            .where(
                Property.lat.is_(None),
                Property.address_ja.isnot(None),
            )
            .limit(limit)
        )
        properties = result.scalars().all()

        stats = {"total": len(properties), "success": 0, "failed": 0, "skipped": 0}

        for prop in properties:
            if not prop.address_ja:
                stats["skipped"] += 1
                continue

            coords = await self.geocode_address(prop.address_ja)

            if coords:
                prop.lat = coords[0]
                prop.lng = coords[1]
                stats["success"] += 1
            else:
                stats["failed"] += 1

            # Rate limiting
            await asyncio.sleep(GEOCODE_DELAY_SECONDS)

        await session.commit()
        logger.info("Batch geocoding complete", **stats)
        return stats

    @staticmethod
    def _simplify_address(address: str) -> str:
        """
        Simplify a Japanese address for better geocoding results.

        Removes building names, room numbers, and other noise that
        can confuse geocoders.
        """
        import re

        # Remove common building/room suffixes
        address = re.sub(r"[（(].*?[）)]", "", address)
        # Remove room numbers
        address = re.sub(r"\s*\d+号室.*$", "", address)
        address = re.sub(r"\s*\d+F.*$", "", address)
        # Remove building names after the block number
        # Japanese addresses typically end with chome-ban-go pattern
        address = re.sub(r"(\d+-\d+-\d+)\s+.*$", r"\1", address)

        return address.strip()


# Singleton instance
_geocoding_service: GeocodingService | None = None


def get_geocoding_service() -> GeocodingService:
    """Get or create the singleton geocoding service."""
    global _geocoding_service
    if _geocoding_service is None:
        _geocoding_service = GeocodingService()
    return _geocoding_service
