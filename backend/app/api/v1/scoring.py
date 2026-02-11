import asyncio

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.scoring import PropertyScore

router = APIRouter()


@router.get("/{property_id}")
async def get_property_score(property_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PropertyScore)
        .where(PropertyScore.property_id == property_id)
        .order_by(PropertyScore.scored_at.desc())
        .limit(1)
    )
    score = result.scalar_one_or_none()
    if not score:
        return {"detail": "No score available for this property"}
    return _score_to_dict(score)


@router.post("/run")
async def trigger_scoring(
    limit: int = Query(100, ge=1, le=500),
):
    """Trigger batch scoring for unscored properties."""
    from app.database import async_session
    from app.services.scoring_engine import ScoringEngine

    async def _run():
        async with async_session() as session:
            engine = ScoringEngine(session)
            return await engine.score_properties_batch(limit=limit)

    asyncio.get_running_loop().create_task(_run())
    return {"status": "started", "message": f"Scoring up to {limit} properties in background"}


@router.post("/run/{property_id}")
async def score_single_property(property_id: str, db: AsyncSession = Depends(get_db)):
    """Score a single property immediately."""
    from app.services.scoring_engine import ScoringEngine

    engine = ScoringEngine(db)
    score = await engine.score_property(property_id)
    if not score:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Property not found or could not be scored")
    await db.commit()
    return _score_to_dict(score)


def _score_to_dict(score: PropertyScore) -> dict:
    return {
        "property_id": str(score.property_id),
        "rebuild_score": float(score.rebuild_score) if score.rebuild_score else None,
        "hazard_score": float(score.hazard_score) if score.hazard_score else None,
        "infrastructure_score": float(score.infrastructure_score) if score.infrastructure_score else None,
        "demographic_score": float(score.demographic_score) if score.demographic_score else None,
        "value_score": float(score.value_score) if score.value_score else None,
        "condition_score": float(score.condition_score) if score.condition_score else None,
        "composite_score": float(score.composite_score),
        "weights": score.weights,
        "scoring_version": score.scoring_version,
        "scored_at": score.scored_at.isoformat() if score.scored_at else None,
    }
