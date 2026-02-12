from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import structlog
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting Japan REIT API", env=settings.app_env)
    # Auto-create scraper infrastructure tables (NOT property data tables)
    from app.database import create_all_tables
    import app.models  # noqa: F401 — ensure all models are registered
    await create_all_tables()

    db_type = "sqlite" if settings.is_sqlite else "supabase/postgresql"
    logger.info("Database ready", backend=db_type)

    # Start periodic scraping scheduler
    from app.tasks.runner import start_scheduler, stop_scheduler
    if settings.scheduler_enabled:
        start_scheduler(interval_hours=settings.scheduler_interval_hours)

    yield

    # Stop scheduler on shutdown
    if settings.scheduler_enabled:
        stop_scheduler()
    logger.info("Shutting down Japan REIT API")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Japan Real Estate Scraper API",
        description="Scraper microservice for JapanPropSearch. Writes to Supabase PostgreSQL.",
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.api.v1.router import api_router

    app.include_router(api_router, prefix="/api/v1")

    # --- Verify API key helper ---
    def _verify_api_key(request: Request):
        api_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
        if not settings.scraper_api_key:
            raise HTTPException(status_code=500, detail="SCRAPER_API_KEY not configured")
        if api_key != settings.scraper_api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")

    # --- Health endpoint (K-06, enriched N-04) ---
    @app.get("/health")
    async def health_check():
        """Enhanced health check: DB connectivity, per-source stats, property count."""
        from app.database import async_session
        from sqlalchemy import select, text, func
        from app.models.scraping import ScrapeJob, ScrapeSource
        from app.models.new_schema import NewProperty, NewPropertyListing

        result = {
            "status": "healthy",
            "version": "2.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": "unknown",
            "property_count": 0,
            "last_scrape": None,
            "sources": [],
            "scheduler_enabled": settings.scheduler_enabled,
            "translate_available": bool(settings.google_translate_api_key),
            "storage_available": bool(settings.supabase_url and settings.supabase_service_role_key),
        }

        try:
            async with async_session() as session:
                await session.execute(text("SELECT 1"))
                result["database"] = "connected"

                # Total property count
                count_result = await session.execute(
                    select(func.count(NewProperty.id))
                )
                result["property_count"] = count_result.scalar() or 0

                # Get last completed scrape (global)
                last_job = await session.execute(
                    select(ScrapeJob)
                    .where(ScrapeJob.status == "completed")
                    .order_by(ScrapeJob.completed_at.desc())
                    .limit(1)
                )
                job = last_job.scalar_one_or_none()
                if job and job.completed_at:
                    result["last_scrape"] = {
                        "source": job.source_id,
                        "completed_at": job.completed_at.isoformat(),
                        "listings_found": job.listings_found,
                        "listings_new": job.listings_new,
                    }

                # Per-source statistics
                sources_result = await session.execute(select(ScrapeSource))
                for source in sources_result.scalars().all():
                    # Count listings from this source
                    listing_count = await session.execute(
                        select(func.count(NewPropertyListing.id)).where(
                            NewPropertyListing.source_id == source.id
                        )
                    )

                    # Last completed job for this source
                    source_last = await session.execute(
                        select(ScrapeJob)
                        .where(ScrapeJob.source_id == source.id, ScrapeJob.status == "completed")
                        .order_by(ScrapeJob.completed_at.desc())
                        .limit(1)
                    )
                    source_job = source_last.scalar_one_or_none()

                    result["sources"].append({
                        "id": source.id,
                        "name": source.display_name,
                        "enabled": source.is_enabled,
                        "listing_count": listing_count.scalar() or 0,
                        "last_scrape_time": source_job.completed_at.isoformat() if source_job and source_job.completed_at else None,
                        "listings_found": source_job.listings_found if source_job else None,
                        "listings_new": source_job.listings_new if source_job else None,
                    })

        except Exception as e:
            result["status"] = "degraded"
            result["database"] = f"error: {str(e)[:100]}"

        return result

    # --- Scrape job status endpoint (N-03) ---
    @app.get("/api/scrape/status/{job_id}")
    async def scrape_status(job_id: str, request: Request):
        """Get real-time status of a scrape job."""
        _verify_api_key(request)

        from app.database import async_session
        from sqlalchemy import select
        from app.models.scraping import ScrapeJob
        from app.tasks.runner import get_task_status

        task_status = get_task_status(job_id)

        async with async_session() as session:
            result = await session.execute(
                select(ScrapeJob).where(ScrapeJob.id == job_id)
            )
            job = result.scalar_one_or_none()
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")

            return {
                "id": str(job.id),
                "source_id": job.source_id,
                "status": job.status,
                "task_running": task_status == "running",
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "listings_found": job.listings_found,
                "listings_new": job.listings_new,
                "listings_updated": job.listings_updated,
                "error_message": job.error_message,
            }

    # --- Scrape job history endpoint (N-03) ---
    @app.get("/api/scrape/history")
    async def scrape_history(request: Request):
        """Get recent scrape job history."""
        _verify_api_key(request)

        from app.database import async_session
        from sqlalchemy import select
        from app.models.scraping import ScrapeJob

        async with async_session() as session:
            result = await session.execute(
                select(ScrapeJob)
                .order_by(ScrapeJob.created_at.desc())
                .limit(20)
            )
            jobs = result.scalars().all()

            return {
                "jobs": [
                    {
                        "id": str(j.id),
                        "source_id": j.source_id,
                        "status": j.status,
                        "started_at": j.started_at.isoformat() if j.started_at else None,
                        "completed_at": j.completed_at.isoformat() if j.completed_at else None,
                        "listings_found": j.listings_found,
                        "listings_new": j.listings_new,
                        "error_message": j.error_message,
                    }
                    for j in jobs
                ],
            }

    # --- Remote trigger endpoint (K-05) ---
    @app.post("/api/scrape/trigger")
    async def remote_trigger(request: Request):
        """Remote trigger endpoint for the Next.js app to start scrape jobs.

        Requires X-API-Key header matching SCRAPER_API_KEY env var.
        """
        _verify_api_key(request)

        body = await request.json()
        source_id = body.get("source_id")
        prefecture_code = body.get("prefecture_code")

        if not source_id:
            raise HTTPException(status_code=400, detail="source_id is required")

        from app.database import async_session
        from sqlalchemy import select
        from app.models.scraping import ScrapeJob, ScrapeSource
        from app.tasks.runner import dispatch_scrape_job

        async with async_session() as session:
            source = await session.get(ScrapeSource, source_id)
            if not source:
                raise HTTPException(status_code=404, detail=f"Source '{source_id}' not found")

            job = ScrapeJob(
                source_id=source_id,
                prefecture_code=prefecture_code,
                status="pending",
                search_params=body.get("search_params", {}),
            )
            session.add(job)
            await session.flush()
            job_id = str(job.id)
            await session.commit()

            dispatch_scrape_job(job_id)

        return {
            "id": job_id,
            "status": "pending",
            "source_id": source_id,
            "message": "Scrape job dispatched",
        }

    return app


app = create_app()
