"""
J-SHIS (Japan Seismic Hazard Information Station) API client.

API Documentation: https://www.j-shis.bosai.go.jp/en/api-list
Base URL: http://www.j-shis.bosai.go.jp/map/api/
Authentication: None required

Available APIs:
- Seismic Hazard Information (pshm)
- Landslide Information
- Hazard Curve
- Average Hazard
- Mesh Search
"""

from typing import Any

from app.clients.base_client import BaseAPIClient


class JShisClient(BaseAPIClient):
    """J-SHIS seismic hazard API client."""

    def __init__(self):
        super().__init__(
            base_url="http://www.j-shis.bosai.go.jp",
            timeout=30.0,
            rate_limit_delay=2.0,
        )

    async def get_seismic_hazard_by_mesh(
        self,
        mesh_code: str,
        version: str = "Y2024",
        case: str = "AVR",
        eq_type: str = "TTL_MTTL",
    ) -> dict[str, Any]:
        """
        Get seismic hazard information for a mesh code.

        Args:
            mesh_code: JIS mesh code (8-10 digits)
            version: Data version year (Y2008-Y2024)
            case: AVR (average) or MAX (maximum)
            eq_type: Earthquake type code (TTL_MTTL = all types combined)

        Returns:
            GeoJSON FeatureCollection with seismic hazard data
        """
        return await self.get(
            f"/map/api/pshm/{version}/{case}/{eq_type}/meshinfo.geojson",
            params={"meshcode": mesh_code},
        )

    async def get_seismic_hazard_by_position(
        self,
        lat: float,
        lng: float,
        version: str = "Y2024",
        case: str = "AVR",
        eq_type: str = "TTL_MTTL",
    ) -> dict[str, Any]:
        """
        Get seismic hazard information for a lat/lng position.

        Args:
            lat: Latitude
            lng: Longitude
            version: Data version year
            case: AVR or MAX
            eq_type: Earthquake type

        Returns:
            GeoJSON FeatureCollection
        """
        return await self.get(
            f"/map/api/pshm/{version}/{case}/{eq_type}/meshinfo.geojson",
            params={
                "position": f"{lng},{lat}",
                "epsg": "4326",
            },
        )

    async def get_hazard_curve(self, mesh_code: str) -> dict[str, Any]:
        """
        Get exceedance probability vs. intensity curve for a mesh.

        Returns hazard curve data showing probability of exceeding
        various seismic intensity levels.
        """
        return await self.get(
            "/map/api/pshm/Y2024/AVR/TTL_MTTL/hazardcurve.geojson",
            params={"meshcode": mesh_code},
        )

    async def get_landslide_risk(
        self,
        lat: float,
        lng: float,
        radius_km: int = 1,
    ) -> dict[str, Any]:
        """
        Get landslide risk information near a position.

        Args:
            lat: Latitude
            lng: Longitude
            radius_km: Search radius in km (0-10)
        """
        return await self.get(
            "/map/api/landslide/meshinfo.geojson",
            params={
                "position": f"{lng},{lat}",
                "epsg": "4326",
                "radius": radius_km,
            },
        )

    async def get_average_hazard(
        self,
        lat: float,
        lng: float,
    ) -> dict[str, Any]:
        """
        Get averaged hazard information at a position.

        Returns site amplification factors, average S-wave velocity,
        and engineering geomorphologic classification.
        """
        return await self.get(
            "/map/api/pshm/Y2024/AVR/TTL_MTTL/avghazard.geojson",
            params={
                "position": f"{lng},{lat}",
                "epsg": "4326",
            },
        )

    async def search_mesh(
        self,
        mesh_code: str,
        radius_km: int | None = None,
    ) -> dict[str, Any]:
        """
        Search for mesh information.

        Args:
            mesh_code: JIS mesh code
            radius_km: Optional search radius
        """
        params: dict[str, Any] = {"meshcode": mesh_code}
        if radius_km is not None:
            params["radius"] = radius_km
        return await self.get("/map/api/meshsearch.geojson", params=params)
