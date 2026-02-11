"""
ScoringEngine -- 6-dimension property scoring for Japanese real estate investment.

Dimensions (each 0-100, weighted):
    Rebuild         25%  Road width, frontage, zoning.  0 = deal killer.
    Hazard          20%  Inverted natural-disaster risk.
    Infrastructure  15%  Station / amenity proximity + use-zone quality.
    Demographic     15%  Population trend (stub until mesh data loaded).
    Value           15%  Price-per-sqm vs investment thresholds.
    Condition       10%  Building age + structure-type depreciation.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.property import Property
from app.models.scoring import PropertyScore
from app.models.hazard import HazardAssessment

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Residential use-zone keywords (Japanese zoning designations)
_RESIDENTIAL_ZONES: set[str] = {
    "第一種低層住居専用地域",
    "第二種低層住居専用地域",
    "第一種中高層住居専用地域",
    "第二種中高層住居専用地域",
    "第一種住居地域",
    "第二種住居地域",
    "準住居地域",
    "田園住居地域",
}

_COMMERCIAL_ZONES: set[str] = {
    "近隣商業地域",
    "商業地域",
}

# Floor-plan pattern: e.g. "3LDK", "4SLDK", "2DK"
_FLOOR_PLAN_RE = re.compile(r"(\d+)\s*[SLDK]+", re.IGNORECASE)


def _get_structure_useful_life(structure: str | None) -> int:
    """Return the statutory useful life (years) based on building structure type.

    Japanese tax depreciation schedules:
        Wood (木造)                 22 years
        Light steel (軽量鉄骨)      27 years
        RC / SRC (鉄筋コンクリート)  47 years

    Falls back to 22 (wood) when the structure string is unknown or absent.
    """
    if not structure:
        return 22  # default: wood

    s = structure.lower()

    # RC / SRC / reinforced concrete
    if any(kw in s for kw in ("鉄筋コンクリート", "rc", "src", "鉄骨鉄筋")):
        return 47

    # Light steel
    if any(kw in s for kw in ("軽量鉄骨", "light steel", "light-steel")):
        return 27

    # Heavy steel
    if any(kw in s for kw in ("重量鉄骨", "鉄骨造", "steel")):
        return 34

    # Wood (default)
    return 22


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    """Clamp *value* to [lo, hi]."""
    return max(lo, min(hi, value))


# ---------------------------------------------------------------------------
# ScoringEngine
# ---------------------------------------------------------------------------


class ScoringEngine:
    """Compute and persist 6-dimension investment scores for properties."""

    SCORING_VERSION = "1.0"

    DEFAULT_WEIGHTS: dict[str, float] = {
        "rebuild": 0.25,
        "hazard": 0.20,
        "infrastructure": 0.15,
        "demographic": 0.15,
        "value": 0.15,
        "condition": 0.10,
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.weights = dict(self.DEFAULT_WEIGHTS)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def score_property(self, property_id: str) -> PropertyScore | None:
        """Score a single property and persist the result.

        Returns the created/updated :class:`PropertyScore`, or ``None`` if the
        property was not found.
        """
        result = await self.session.execute(
            select(Property).where(Property.id == property_id)
        )
        prop = result.scalar_one_or_none()
        if prop is None:
            logger.warning("scoring.property_not_found", property_id=property_id)
            return None

        # Compute each dimension
        rebuild = self._score_rebuild(prop)
        hazard = await self._score_hazard(prop)
        infrastructure = self._score_infrastructure(prop)
        demographic = self._score_demographic(prop)
        value = self._score_value(prop)
        condition = self._score_condition(prop)

        # Weighted composite
        composite = (
            rebuild * self.weights["rebuild"]
            + hazard * self.weights["hazard"]
            + infrastructure * self.weights["infrastructure"]
            + demographic * self.weights["demographic"]
            + value * self.weights["value"]
            + condition * self.weights["condition"]
        )
        composite = round(_clamp(composite), 2)

        # Upsert PropertyScore -------------------------------------------------
        # Check for existing score with the same version
        existing_result = await self.session.execute(
            select(PropertyScore).where(
                PropertyScore.property_id == property_id,
                PropertyScore.scoring_version == self.SCORING_VERSION,
            )
        )
        score_record = existing_result.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if score_record is None:
            score_record = PropertyScore(
                property_id=property_id,
                rebuild_score=round(rebuild, 2),
                hazard_score=round(hazard, 2),
                infrastructure_score=round(infrastructure, 2),
                demographic_score=round(demographic, 2),
                value_score=round(value, 2),
                condition_score=round(condition, 2),
                weights=self.weights,
                composite_score=composite,
                scoring_version=self.SCORING_VERSION,
                scored_at=now,
            )
            self.session.add(score_record)
        else:
            score_record.rebuild_score = round(rebuild, 2)
            score_record.hazard_score = round(hazard, 2)
            score_record.infrastructure_score = round(infrastructure, 2)
            score_record.demographic_score = round(demographic, 2)
            score_record.value_score = round(value, 2)
            score_record.condition_score = round(condition, 2)
            score_record.weights = self.weights
            score_record.composite_score = composite
            score_record.scored_at = now

        # Update the denormalised composite on Property itself
        prop.composite_score = composite
        prop.score_updated_at = now

        await self.session.flush()

        logger.info(
            "scoring.property_scored",
            property_id=property_id,
            composite=composite,
            rebuild=round(rebuild, 2),
            hazard=round(hazard, 2),
            infrastructure=round(infrastructure, 2),
            demographic=round(demographic, 2),
            value=round(value, 2),
            condition=round(condition, 2),
        )

        return score_record

    async def score_properties_batch(self, limit: int = 100) -> int:
        """Score properties that have not yet been scored (or have an older version).

        Returns the number of properties scored.
        """
        # Sub-query: property_ids already scored with the current version
        scored_subq = (
            select(PropertyScore.property_id)
            .where(PropertyScore.scoring_version == self.SCORING_VERSION)
            .subquery()
        )

        result = await self.session.execute(
            select(Property.id)
            .where(Property.id.notin_(select(scored_subq.c.property_id)))
            .where(Property.status == "active")
            .limit(limit)
        )
        property_ids: list[str] = list(result.scalars().all())

        scored_count = 0
        for pid in property_ids:
            score = await self.score_property(pid)
            if score is not None:
                scored_count += 1

        logger.info(
            "scoring.batch_complete",
            requested=len(property_ids),
            scored=scored_count,
            version=self.SCORING_VERSION,
        )
        return scored_count

    # ------------------------------------------------------------------
    # Dimension scoring methods (each returns 0-100)
    # ------------------------------------------------------------------

    def _score_rebuild(self, prop: Property) -> float:
        """Rebuild-ability score.

        This is a *deal-killer* dimension: if the property is explicitly
        flagged as un-rebuildable the score is 0, which drags the composite
        down hard.
        """
        # Deal killer
        if prop.rebuild_possible is False:
            return 0.0

        # Baseline: if rebuild_possible is explicitly True we start at 80;
        # if it is None (unknown) we start at 50.
        score = 80.0 if prop.rebuild_possible is True else 50.0

        # --- Road width contribution (max 20 pts) ---
        if prop.road_width_m is not None:
            road_w = float(prop.road_width_m)
            if road_w >= 4.0:
                score += 20.0  # Building Standards Act requirement met
            elif road_w >= 3.0:
                score += 10.0  # Marginal -- setback likely required
            # < 3 m  -> +0
        else:
            # Unknown road width -> small deduction from the base
            score -= 10.0

        # --- Road frontage contribution (max 20 pts) ---
        if prop.road_frontage_m is not None:
            frontage = float(prop.road_frontage_m)
            if frontage >= 2.0:
                score += 20.0  # Statutory minimum met
            # < 2 m  -> +0
        else:
            score -= 10.0

        # --- Zoning bonus ---
        if prop.use_zone in _RESIDENTIAL_ZONES:
            score += 5.0
        elif prop.use_zone in _COMMERCIAL_ZONES:
            score += 3.0

        # Clamp because deductions may push below zero on unknown data
        return _clamp(score)

    async def _score_hazard(self, prop: Property) -> float:
        """Natural-hazard risk score (inverted: lower risk = higher score).

        Four sub-dimensions contribute up to 25 pts each (total 100).
        """
        result = await self.session.execute(
            select(HazardAssessment).where(
                HazardAssessment.property_id == prop.id
            )
        )
        hazard = result.scalar_one_or_none()

        if hazard is None:
            return 50.0  # Neutral -- no data available

        score = 0.0

        # --- Flood (max 25) ---
        if hazard.flood_depth_max_m is not None:
            depth = float(hazard.flood_depth_max_m)
            if depth <= 0.0:
                score += 25.0
            elif depth < 0.5:
                score += 20.0
            elif depth < 1.0:
                score += 15.0
            elif depth < 3.0:
                score += 5.0
            # >= 3 m -> +0
        else:
            score += 12.5  # Neutral sub-score when data is missing

        # --- Seismic / PGA (max 25) ---
        if hazard.pga_475yr is not None:
            pga = float(hazard.pga_475yr)
            if pga < 1.5:
                score += 25.0
            elif pga < 2.0:
                score += 20.0
            elif pga < 2.5:
                score += 15.0
            else:
                score += 5.0
        else:
            score += 12.5

        # --- Landslide (max 25) ---
        if hazard.landslide_risk is not None:
            risk = hazard.landslide_risk.lower()
            if risk in ("low", "none"):
                score += 25.0
            elif risk == "medium":
                score += 15.0
            elif risk == "high":
                score += 5.0
            elif risk == "very_high":
                score += 0.0
            else:
                score += 12.5  # Unrecognised label
        else:
            score += 12.5

        # --- Tsunami (max 25) ---
        if hazard.tsunami_depth_max_m is not None:
            t_depth = float(hazard.tsunami_depth_max_m)
            if t_depth <= 0.0:
                score += 25.0
            elif t_depth < 0.5:
                score += 20.0
            elif t_depth < 1.0:
                score += 15.0
            elif t_depth < 3.0:
                score += 5.0
            # >= 3 m -> +0
        else:
            score += 12.5

        return _clamp(score)

    def _score_infrastructure(self, prop: Property) -> float:
        """Infrastructure / amenity proximity score.

        Until detailed POI data is integrated this is a heuristic based on
        available columns: lat/lng presence, use-zone type, and floor plan.
        """
        if prop.latitude is None or prop.longitude is None:
            return 50.0  # Cannot evaluate without coordinates

        score = 50.0  # Base: coordinates present

        # Use-zone quality bonus
        if prop.use_zone in _COMMERCIAL_ZONES:
            score += 20.0  # Commercial zones tend to be well-served
        elif prop.use_zone in _RESIDENTIAL_ZONES:
            score += 10.0

        # Floor plan quality (proxy for liveability)
        if prop.floor_plan:
            m = _FLOOR_PLAN_RE.search(prop.floor_plan)
            if m:
                rooms = int(m.group(1))
                if rooms >= 4:
                    score += 15.0
                elif rooms >= 3:
                    score += 10.0
                elif rooms >= 2:
                    score += 5.0

            # LDK presence (living-dining-kitchen) is a quality signal
            if "ldk" in prop.floor_plan.lower():
                score += 5.0

        return _clamp(score)

    def _score_demographic(self, prop: Property) -> float:  # noqa: ARG002
        """Demographic trend score.

        Currently returns a neutral 50.  Will be enhanced once reinfolib
        population mesh data (PopulationMesh model) is loaded and queryable.
        """
        return 50.0

    def _score_value(self, prop: Property) -> float:
        """Investment value score based on price per square metre.

        Lower price/sqm is better for investment (rural akiya strategy).
        Thresholds are calibrated for the Japanese countryside market.
        """
        if prop.price is None or prop.land_area_sqm is None:
            return 50.0  # Cannot evaluate

        land_area = float(prop.land_area_sqm)
        if land_area <= 0:
            return 50.0

        price_per_sqm = prop.price / land_area

        if price_per_sqm < 10_000:
            return 90.0
        elif price_per_sqm < 20_000:
            return 80.0
        elif price_per_sqm < 50_000:
            return 70.0
        elif price_per_sqm < 100_000:
            return 50.0
        else:
            return 30.0

    def _score_condition(self, prop: Property) -> float:
        """Building condition score based on age and structure type.

        Uses Japanese tax depreciation useful-life tables.  A base score of 30
        is always awarded (representing underlying land value).
        """
        if prop.year_built is None:
            return 40.0  # Unknown age -- slightly below neutral

        current_year = datetime.now(timezone.utc).year
        age = current_year - prop.year_built

        if age < 0:
            # Future year_built -- data quality issue; treat as new
            age = 0

        useful_life = _get_structure_useful_life(prop.structure)
        remaining_life_pct = max(0.0, (useful_life - age) / useful_life)

        # 70 pts from remaining-life percentage + 30 pts base (land value)
        score = remaining_life_pct * 70.0 + 30.0

        return _clamp(score)
