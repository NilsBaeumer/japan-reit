"""
GSI Hazard Map Portal (disaportal.gsi.go.jp) - WMS/WMTS tile proxy.

Provides raster tile access for hazard overlays:
- Flood risk (洪水浸水想定区域)
- Tsunami risk (津波浸水想定)
- Landslide risk (土砂災害警戒区域)
- Storm surge (高潮浸水想定区域)
"""

from app.clients.base_client import BaseAPIClient


# Known tile layer URLs from GSI Hazard Map Portal
HAZARD_TILE_LAYERS = {
    "flood": (
        "https://disaportaldata.gsi.go.jp/raster/01_flood_l2_shinsuishin_data/{z}/{x}/{y}.png"
    ),
    "tsunami": (
        "https://disaportaldata.gsi.go.jp/raster/04_tsunami_newlegend_data/{z}/{x}/{y}.png"
    ),
    "landslide": (
        "https://disaportaldata.gsi.go.jp/raster/05_dosekiryukeikaikuiki/{z}/{x}/{y}.png"
    ),
    "steep_slope": (
        "https://disaportaldata.gsi.go.jp/raster/05_kyukeishachikuzure/{z}/{x}/{y}.png"
    ),
    "storm_surge": (
        "https://disaportaldata.gsi.go.jp/raster/03_hightide_l2_shinsuishin_data/{z}/{x}/{y}.png"
    ),
}


class HazardMapClient(BaseAPIClient):
    """GSI Hazard Map Portal tile fetcher."""

    def __init__(self):
        super().__init__(
            base_url="https://disaportaldata.gsi.go.jp",
            timeout=15.0,
            rate_limit_delay=0.5,
        )

    async def get_tile(self, layer: str, z: int, x: int, y: int) -> bytes | None:
        """
        Fetch a hazard map raster tile.

        Args:
            layer: Layer name ('flood', 'tsunami', 'landslide', 'steep_slope', 'storm_surge')
            z: Zoom level
            x: Tile x coordinate
            y: Tile y coordinate

        Returns:
            PNG image bytes or None if tile doesn't exist
        """
        url_template = HAZARD_TILE_LAYERS.get(layer)
        if not url_template:
            raise ValueError(f"Unknown hazard layer: {layer}")

        url = url_template.format(z=z, x=x, y=y)

        try:
            return await self.get_bytes(url)
        except Exception:
            # Tiles outside coverage area return 404, which is normal
            return None

    @staticmethod
    def get_available_layers() -> list[dict[str, str]]:
        """List available hazard map layers."""
        return [
            {"id": "flood", "name": "Flood Risk (洪水浸水想定)", "name_ja": "洪水浸水想定区域"},
            {"id": "tsunami", "name": "Tsunami Risk (津波浸水想定)", "name_ja": "津波浸水想定"},
            {"id": "landslide", "name": "Landslide Risk (土砂災害)", "name_ja": "土砂災害警戒区域"},
            {"id": "steep_slope", "name": "Steep Slope (急傾斜)", "name_ja": "急傾斜地崩壊危険区域"},
            {"id": "storm_surge", "name": "Storm Surge (高潮)", "name_ja": "高潮浸水想定区域"},
        ]

    @staticmethod
    def get_tile_url(layer: str) -> str | None:
        """Get tile URL template for a layer (for frontend direct access)."""
        return HAZARD_TILE_LAYERS.get(layer)
