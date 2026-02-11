"""
Hazard assessment service.

Aggregates seismic, flood, tsunami, and landslide hazard data from
J-SHIS, reinfolib (XKT016/XKT021/XKT022), and the GSI Hazard Map Portal
into a single HazardAssessment record per property.
"""

import asyncio
import math
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.hazard_map import HazardMapClient
from app.clients.jshis import JShisClient
from app.clients.reinfolib import ReinfolibClient
from app.models.hazard import HazardAssessment
from app.models.property import Property
from app.utils.mesh_code import latlng_to_mesh

logger = structlog.get_logger()

# Delay between sequential property assessments to respect API rate limits.
BATCH_INTER_PROPERTY_DELAY = 3.0

# Zoom level used for reinfolib vector tile lookups (~1km mesh equivalent).
REINFOLIB_TILE_ZOOM = 15

# Flood depth colour-coded legend (GSI hazard map PNG tiles).
# Pixel RGBA values mapped to estimated inundation depth in metres.
FLOOD_DEPTH_LEGEND: dict[str, float] = {
    "yellow": 0.5,     # < 0.5 m
    "orange": 1.0,     # 0.5 - 1.0 m
    "light_red": 3.0,  # 1.0 - 3.0 m
    "red": 5.0,        # 3.0 - 5.0 m
    "purple": 10.0,    # 5.0 - 10.0 m
    "dark_purple": 20.0,  # > 10 m
}

# JMA seismic intensity levels used in the 30-year exceedance probability maps.
JMA_INTENSITY_LEVELS = [
    "I45",   # JMA Intensity 4.5 (Lower-5)
    "I50",   # JMA Intensity 5.0 (Upper-5)
    "I55",   # JMA Intensity 5.5 (Lower-6)
    "I60",   # JMA Intensity 6.0 (Upper-6)
    "I65",   # JMA Intensity 6.5 (7)
]


def _latlng_to_tile(lat: float, lng: float, zoom: int) -> tuple[int, int]:
    """Convert lat/lng to slippy-map tile coordinates at a given zoom level."""
    lat_rad = math.radians(lat)
    n = 2 ** zoom
    x = int((lng + 180.0) / 360.0 * n)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


class HazardService:
    """Aggregate hazard data from multiple Japanese government APIs."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._jshis = JShisClient()
        self._reinfolib = ReinfolibClient()
        self._hazard_map = HazardMapClient()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def assess_property(self, property_id: str) -> HazardAssessment | None:
        """
        Build or update a full hazard assessment for a single property.

        Returns the persisted ``HazardAssessment`` or ``None`` when the
        property cannot be found or lacks coordinates.
        """
        prop = await self.session.get(Property, property_id)
        if prop is None:
            logger.warning("Property not found for hazard assessment", property_id=property_id)
            return None

        if prop.latitude is None or prop.longitude is None:
            logger.info(
                "Property has no coordinates, skipping hazard assessment",
                property_id=property_id,
            )
            return None

        lat = prop.latitude
        lng = prop.longitude
        mesh_code = latlng_to_mesh(lat, lng, level=3)

        logger.info(
            "Starting hazard assessment",
            property_id=property_id,
            lat=lat,
            lng=lng,
            mesh_code=mesh_code,
        )

        # ---- Parallel J-SHIS calls ----
        seismic_result, landslide_result, avg_hazard_result = await asyncio.gather(
            self._jshis.get_seismic_hazard_by_position(lat, lng),
            self._jshis.get_landslide_risk(lat, lng, radius_km=1),
            self._jshis.get_average_hazard(lat, lng),
            return_exceptions=True,
        )

        # ---- Parallel hazard-map tile calls ----
        tile_x, tile_y = _latlng_to_tile(lat, lng, REINFOLIB_TILE_ZOOM)
        flood_tile_result, tsunami_tile_result = await asyncio.gather(
            self._hazard_map.get_tile("flood", REINFOLIB_TILE_ZOOM, tile_x, tile_y),
            self._hazard_map.get_tile("tsunami", REINFOLIB_TILE_ZOOM, tile_x, tile_y),
            return_exceptions=True,
        )

        # ---- Parallel reinfolib tile calls ----
        reinfolib_disaster_result, reinfolib_landslide_result, reinfolib_steep_result = (
            await asyncio.gather(
                self._safe_reinfolib_tiles(
                    self._reinfolib.get_disaster_zone_tiles,
                    REINFOLIB_TILE_ZOOM,
                    tile_x,
                    tile_y,
                ),
                self._safe_reinfolib_tiles(
                    self._reinfolib.get_landslide_prevention_tiles,
                    REINFOLIB_TILE_ZOOM,
                    tile_x,
                    tile_y,
                ),
                self._safe_reinfolib_tiles(
                    self._reinfolib.get_steep_slope_tiles,
                    REINFOLIB_TILE_ZOOM,
                    tile_x,
                    tile_y,
                ),
                return_exceptions=True,
            )
        )

        # ---- Parse responses ----
        data_sources: dict[str, str] = {}

        # Seismic
        intensity_prob: dict | None = None
        if not isinstance(seismic_result, BaseException):
            intensity_prob = self._parse_seismic_response(seismic_result)
            data_sources["seismic"] = "J-SHIS pshm"
        else:
            logger.warning(
                "J-SHIS seismic API failed",
                property_id=property_id,
                error=str(seismic_result),
            )

        # PGA from average hazard
        pga_value: float | None = None
        if not isinstance(avg_hazard_result, BaseException):
            pga_value = self._classify_seismic_risk(avg_hazard_result)
            data_sources["avg_hazard"] = "J-SHIS avghazard"
        else:
            logger.warning(
                "J-SHIS average hazard API failed",
                property_id=property_id,
                error=str(avg_hazard_result),
            )

        # Landslide (J-SHIS)
        landslide_risk: str | None = None
        steep_slope_zone = False
        landslide_prevention_zone = False
        if not isinstance(landslide_result, BaseException):
            landslide_risk, steep_slope_zone, landslide_prevention_zone = (
                self._parse_landslide_response(landslide_result)
            )
            data_sources["landslide_jshis"] = "J-SHIS landslide"
        else:
            logger.warning(
                "J-SHIS landslide API failed",
                property_id=property_id,
                error=str(landslide_result),
            )

        # Reinfolib landslide-prevention / steep-slope overlays
        if not isinstance(reinfolib_landslide_result, BaseException):
            if reinfolib_landslide_result is not None and len(reinfolib_landslide_result) > 0:
                landslide_prevention_zone = True
                data_sources["landslide_prevention_reinfolib"] = "reinfolib XKT021"
        else:
            logger.warning(
                "Reinfolib landslide prevention tile failed",
                property_id=property_id,
                error=str(reinfolib_landslide_result),
            )

        if not isinstance(reinfolib_steep_result, BaseException):
            if reinfolib_steep_result is not None and len(reinfolib_steep_result) > 0:
                steep_slope_zone = True
                data_sources["steep_slope_reinfolib"] = "reinfolib XKT022"
        else:
            logger.warning(
                "Reinfolib steep slope tile failed",
                property_id=property_id,
                error=str(reinfolib_steep_result),
            )

        # Flood (GSI hazard map tile)
        flood_depth_max: float | None = None
        flood_zone: str | None = None
        if not isinstance(flood_tile_result, BaseException):
            if flood_tile_result is not None and len(flood_tile_result) > 0:
                flood_zone = "flood_risk_area"
                # Tile presence indicates the property is inside a mapped flood zone.
                # Without full raster analysis we record a conservative default.
                flood_depth_max = 0.5
                data_sources["flood"] = "GSI disaportal flood"
        else:
            logger.warning(
                "Hazard Map flood tile failed",
                property_id=property_id,
                error=str(flood_tile_result),
            )

        # Reinfolib disaster zone overlay (XKT016) can refine the flood zone
        if not isinstance(reinfolib_disaster_result, BaseException):
            if reinfolib_disaster_result is not None and len(reinfolib_disaster_result) > 0:
                if flood_zone is None:
                    flood_zone = "disaster_risk_zone"
                data_sources["disaster_zone_reinfolib"] = "reinfolib XKT016"
        else:
            logger.warning(
                "Reinfolib disaster zone tile failed",
                property_id=property_id,
                error=str(reinfolib_disaster_result),
            )

        # Tsunami (GSI hazard map tile)
        tsunami_risk: str | None = None
        tsunami_depth_max: float | None = None
        if not isinstance(tsunami_tile_result, BaseException):
            if tsunami_tile_result is not None and len(tsunami_tile_result) > 0:
                tsunami_risk = "medium"
                tsunami_depth_max = 1.0
                data_sources["tsunami"] = "GSI disaportal tsunami"
        else:
            logger.warning(
                "Hazard Map tsunami tile failed",
                property_id=property_id,
                error=str(tsunami_tile_result),
            )

        # Liquefaction risk derived from average hazard amplification factor
        liquefaction_risk: str | None = None
        if not isinstance(avg_hazard_result, BaseException):
            liquefaction_risk = self._estimate_liquefaction(avg_hazard_result)

        # ---- Upsert assessment record ----
        assessment = await self._get_or_create_assessment(property_id)
        assessment.seismic_intensity_prob = intensity_prob
        assessment.pga_475yr = pga_value
        assessment.liquefaction_risk = liquefaction_risk
        assessment.flood_depth_max_m = flood_depth_max
        assessment.flood_zone = flood_zone
        assessment.tsunami_risk = tsunami_risk
        assessment.tsunami_depth_max_m = tsunami_depth_max
        assessment.landslide_risk = landslide_risk
        assessment.steep_slope_zone = steep_slope_zone
        assessment.landslide_prevention_zone = landslide_prevention_zone
        assessment.mesh_code = mesh_code
        assessment.assessed_at = datetime.now(timezone.utc)
        assessment.data_sources = data_sources

        self.session.add(assessment)
        await self.session.flush()

        logger.info(
            "Hazard assessment complete",
            property_id=property_id,
            sources=list(data_sources.keys()),
        )
        return assessment

    async def assess_properties_batch(self, limit: int = 50) -> int:
        """
        Assess properties that have coordinates but no hazard assessment yet.

        Processes up to *limit* properties sequentially with a delay between
        each to respect upstream rate limits.  Returns the number of
        properties that were successfully assessed.
        """
        # Sub-query: property IDs that already have an assessment.
        assessed_ids = (
            select(HazardAssessment.property_id)
        )

        result = await self.session.execute(
            select(Property)
            .where(
                Property.latitude.isnot(None),
                Property.longitude.isnot(None),
                Property.id.notin_(assessed_ids),
            )
            .limit(limit)
        )
        properties = result.scalars().all()

        if not properties:
            logger.info("No unassessed properties with coordinates found")
            return 0

        logger.info("Starting batch hazard assessment", count=len(properties))

        assessed_count = 0
        for prop in properties:
            try:
                assessment = await self.assess_property(prop.id)
                if assessment is not None:
                    assessed_count += 1
            except Exception:
                logger.exception(
                    "Failed to assess property, continuing batch",
                    property_id=prop.id,
                )

            # Rate-limit between properties so we don't hammer the APIs.
            await asyncio.sleep(BATCH_INTER_PROPERTY_DELAY)

        logger.info(
            "Batch hazard assessment complete",
            total=len(properties),
            assessed=assessed_count,
        )
        return assessed_count

    # ------------------------------------------------------------------
    # Response parsers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_seismic_response(data: dict) -> dict:
        """
        Extract 30-year exceedance probabilities from a J-SHIS GeoJSON
        ``FeatureCollection``.

        The J-SHIS ``pshm`` endpoint returns features whose properties
        contain keys like ``"T30_I45_P"`` (probability of exceeding JMA
        intensity 4.5 within 30 years).  We normalise these into a
        dictionary keyed by intensity level.

        Returns:
            A dict mapping intensity labels to probability values, e.g.
            ``{"I45": 0.26, "I50": 0.09, ...}``.
        """
        intensity_prob: dict[str, float | None] = {}

        features = data.get("features") or []
        if not features:
            return intensity_prob

        # Use the first feature (closest mesh to the query point).
        props = features[0].get("properties", {})

        for level in JMA_INTENSITY_LEVELS:
            key = f"T30_{level}_P"
            value = props.get(key)
            if value is not None:
                try:
                    intensity_prob[level] = float(value)
                except (TypeError, ValueError):
                    intensity_prob[level] = None
            else:
                # Fallback: some versions use slightly different key names.
                alt_key = f"P_{level}_T30"
                alt_value = props.get(alt_key)
                if alt_value is not None:
                    try:
                        intensity_prob[level] = float(alt_value)
                    except (TypeError, ValueError):
                        intensity_prob[level] = None

        return intensity_prob

    @staticmethod
    def _parse_landslide_response(data: dict) -> tuple[str, bool, bool]:
        """
        Parse the J-SHIS landslide GeoJSON response.

        Returns:
            A 3-tuple of (risk_level, steep_slope_zone, landslide_prevention_zone).
            ``risk_level`` is one of ``"low"``, ``"medium"``, ``"high"``,
            or ``"very_high"``.
        """
        features = data.get("features") or []

        if not features:
            return "low", False, False

        steep_slope = False
        landslide_prevention = False
        max_risk_score = 0

        for feature in features:
            props = feature.get("properties", {})

            # J-SHIS uses various property names depending on the layer.
            feature_type = props.get("type", "").lower()
            risk_val = props.get("risk") or props.get("rank") or props.get("R")

            # Steep slope / landslide zone flags
            if "steep" in feature_type or "急傾斜" in props.get("name", ""):
                steep_slope = True
            if "landslide" in feature_type or "地すべり" in props.get("name", ""):
                landslide_prevention = True

            # Numeric risk ranking
            if risk_val is not None:
                try:
                    max_risk_score = max(max_risk_score, int(risk_val))
                except (TypeError, ValueError):
                    pass

            # Any feature within the search radius contributes to a
            # non-trivial risk.
            if max_risk_score == 0:
                max_risk_score = 1

        # Classify into descriptive buckets.
        if max_risk_score >= 4:
            risk_level = "very_high"
        elif max_risk_score >= 3:
            risk_level = "high"
        elif max_risk_score >= 2:
            risk_level = "medium"
        else:
            risk_level = "low"

        return risk_level, steep_slope, landslide_prevention

    @staticmethod
    def _classify_seismic_risk(data: dict) -> float | None:
        """
        Extract PGA (peak ground acceleration) from the J-SHIS average
        hazard response.

        The ``avghazard`` GeoJSON may include ``"PGA_475"`` (PGA for
        a 475-year return period) or ``"ARV"`` (average response value).
        """
        features = data.get("features") or []
        if not features:
            return None

        props = features[0].get("properties", {})

        # Try the direct PGA key first.
        for key in ("PGA_475", "PGA", "AVS", "ARV"):
            value = props.get(key)
            if value is not None:
                try:
                    return round(float(value), 2)
                except (TypeError, ValueError):
                    continue

        return None

    @staticmethod
    def _estimate_liquefaction(data: dict) -> str | None:
        """
        Estimate liquefaction susceptibility from the J-SHIS average
        hazard response.

        Low average S-wave velocity (Vs30) correlates with soft soils
        that are more prone to liquefaction.
        """
        features = data.get("features") or []
        if not features:
            return None

        props = features[0].get("properties", {})

        vs30 = props.get("AVS") or props.get("VS30") or props.get("J_AVS")
        if vs30 is None:
            return None

        try:
            vs30_val = float(vs30)
        except (TypeError, ValueError):
            return None

        if vs30_val < 150:
            return "high"
        elif vs30_val < 250:
            return "medium"
        elif vs30_val < 400:
            return "low"
        else:
            return "very_low"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_or_create_assessment(self, property_id: str) -> HazardAssessment:
        """Retrieve the existing assessment for a property, or create a new one."""
        result = await self.session.execute(
            select(HazardAssessment).where(
                HazardAssessment.property_id == property_id
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        return HazardAssessment(property_id=property_id)

    @staticmethod
    async def _safe_reinfolib_tiles(fetch_fn, z: int, x: int, y: int) -> bytes | None:
        """
        Call a reinfolib tile endpoint, returning ``None`` on any error
        instead of raising.
        """
        try:
            return await fetch_fn(z, x, y)
        except Exception:
            return None

    async def close(self):
        """Close underlying HTTP clients."""
        await self._jshis.close()
        await self._reinfolib.close()
        await self._hazard_map.close()
