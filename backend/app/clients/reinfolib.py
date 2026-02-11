"""
MLIT Real Estate Information Library (reinfolib) API client.

API Documentation: https://www.reinfolib.mlit.go.jp/help/apiManual/
Authentication: Ocp-Apim-Subscription-Key header

Key endpoints:
- XIT001: Transaction/contract price data
- XIT002: Municipality list
- XPT001/002: Land price vector tiles
- XKT004-006: Schools (elementary, middle, high)
- XKT010: Medical facilities
- XKT013: 500m mesh population projections
- XKT015: Rail stations
- XKT016: Disaster risk zones
- XKT021: Landslide prevention areas
- XKT022: Steep slope collapse risk areas
"""

from typing import Any

from app.clients.base_client import BaseAPIClient
from app.config import settings


class ReinfolibClient(BaseAPIClient):
    """MLIT reinfolib API client."""

    def __init__(self):
        super().__init__(
            base_url="https://www.reinfolib.mlit.go.jp",
            headers={"Ocp-Apim-Subscription-Key": settings.reinfolib_api_key},
            timeout=30.0,
            rate_limit_delay=5.0,  # MLIT guidance: conservative rate limiting
        )

    async def get_transactions(self, year: int, city_code: str) -> list[dict[str, Any]]:
        """
        XIT001 - Transaction price data.

        Args:
            year: Year (e.g. 2023)
            city_code: 5-digit municipality code (e.g. "13101" for Chiyoda-ku)

        Returns:
            List of transaction records
        """
        data = await self.get(
            "/ex-api/external/XIT001",
            params={"year": year, "city": city_code},
        )
        return data.get("data", [])

    async def get_municipalities(self, prefecture_code: str) -> list[dict[str, Any]]:
        """
        XIT002 - Municipality list for a prefecture.

        Args:
            prefecture_code: 2-digit prefecture code (e.g. "13" for Tokyo)

        Returns:
            List of municipality records with codes and names
        """
        data = await self.get(
            "/ex-api/external/XIT002",
            params={"area": prefecture_code},
        )
        return data.get("data", [])

    async def get_land_price_tiles(self, z: int, x: int, y: int) -> bytes:
        """XPT001 - Land price point vector tiles (PBF)."""
        return await self.get_bytes(f"/ex-api/external/XPT001/{z}/{x}/{y}.pbf")

    async def get_price_indicator_tiles(self, z: int, x: int, y: int) -> bytes:
        """XPT002 - Price indicator vector tiles (PBF)."""
        return await self.get_bytes(f"/ex-api/external/XPT002/{z}/{x}/{y}.pbf")

    async def get_school_tiles(self, school_type: str, z: int, x: int, y: int) -> bytes:
        """
        School facility tiles.
        school_type: 'XKT004' (elementary), 'XKT005' (middle), 'XKT006' (high school)
        """
        return await self.get_bytes(f"/ex-api/external/{school_type}/{z}/{x}/{y}.pbf")

    async def get_medical_tiles(self, z: int, x: int, y: int) -> bytes:
        """XKT010 - Medical facility tiles."""
        return await self.get_bytes(f"/ex-api/external/XKT010/{z}/{x}/{y}.pbf")

    async def get_population_mesh_tiles(self, z: int, x: int, y: int) -> bytes:
        """XKT013 - 500m mesh population projection tiles."""
        return await self.get_bytes(f"/ex-api/external/XKT013/{z}/{x}/{y}.pbf")

    async def get_station_tiles(self, z: int, x: int, y: int) -> bytes:
        """XKT015 - Rail station tiles."""
        return await self.get_bytes(f"/ex-api/external/XKT015/{z}/{x}/{y}.pbf")

    async def get_disaster_zone_tiles(self, z: int, x: int, y: int) -> bytes:
        """XKT016 - Disaster risk zone tiles."""
        return await self.get_bytes(f"/ex-api/external/XKT016/{z}/{x}/{y}.pbf")

    async def get_landslide_prevention_tiles(self, z: int, x: int, y: int) -> bytes:
        """XKT021 - Landslide prevention area tiles."""
        return await self.get_bytes(f"/ex-api/external/XKT021/{z}/{x}/{y}.pbf")

    async def get_steep_slope_tiles(self, z: int, x: int, y: int) -> bytes:
        """XKT022 - Steep slope collapse risk area tiles."""
        return await self.get_bytes(f"/ex-api/external/XKT022/{z}/{x}/{y}.pbf")
