from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.scraping import ScrapeJob, ScrapeSource
from app.tasks.runner import dispatch_scrape_job

# Ensure all scrapers are registered
import app.scrapers  # noqa: F401

router = APIRouter()


class CreateScrapeJobRequest(BaseModel):
    source_id: str
    prefecture_code: str | None = None
    municipality_code: str | None = None
    search_params: dict | None = None


@router.get("/sources")
async def list_sources(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScrapeSource).order_by(ScrapeSource.id))
    sources = result.scalars().all()
    return [
        {
            "id": s.id,
            "display_name": s.display_name,
            "base_url": s.base_url,
            "is_enabled": s.is_enabled,
            "default_interval_hours": s.default_interval_hours,
        }
        for s in sources
    ]


@router.get("/jobs")
async def list_jobs(
    source_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    query = select(ScrapeJob).order_by(ScrapeJob.created_at.desc()).limit(limit)
    if source_id:
        query = query.where(ScrapeJob.source_id == source_id)
    if status:
        query = query.where(ScrapeJob.status == status)
    result = await db.execute(query)
    jobs = result.scalars().all()
    return [
        {
            "id": str(j.id),
            "source_id": j.source_id,
            "status": j.status,
            "prefecture_code": j.prefecture_code,
            "municipality_code": j.municipality_code,
            "listings_found": j.listings_found,
            "listings_new": j.listings_new,
            "listings_updated": j.listings_updated,
            "error_message": j.error_message,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in jobs
    ]


@router.post("/jobs")
async def create_job(req: CreateScrapeJobRequest, db: AsyncSession = Depends(get_db)):
    # Verify source exists
    source = await db.get(ScrapeSource, req.source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Source '{req.source_id}' not found")

    job = ScrapeJob(
        source_id=req.source_id,
        prefecture_code=req.prefecture_code,
        municipality_code=req.municipality_code,
        search_params=req.search_params or {},
        status="pending",
    )
    db.add(job)
    await db.flush()

    dispatch_scrape_job(str(job.id))

    return {"id": str(job.id), "status": "pending", "message": "Scrape job created"}


@router.post("/scheduler/start")
async def start_scheduler(interval_hours: float = 6.0):
    """Start the periodic scraping scheduler."""
    from app.tasks.runner import start_scheduler as _start
    _start(interval_hours=interval_hours)
    return {"status": "started", "interval_hours": interval_hours}


@router.post("/scheduler/stop")
async def stop_scheduler():
    """Stop the periodic scraping scheduler."""
    from app.tasks.runner import stop_scheduler as _stop
    _stop()
    return {"status": "stopped"}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScrapeJob).where(ScrapeJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": str(job.id),
        "source_id": job.source_id,
        "status": job.status,
        "prefecture_code": job.prefecture_code,
        "municipality_code": job.municipality_code,
        "search_params": job.search_params,
        "listings_found": job.listings_found,
        "listings_new": job.listings_new,
        "listings_updated": job.listings_updated,
        "error_message": job.error_message,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }
