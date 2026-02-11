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

    # --- Health endpoint (K-06) ---
    @app.get("/health")
    async def health_check():
        """Enhanced health check: DB connectivity, last scrape time, service status."""
        from app.database import async_session
        from sqlalchemy import select, text
        from app.models.scraping import ScrapeJob

        result = {
            "status": "healthy",
            "version": "2.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": "unknown",
            "last_scrape": None,
            "scheduler_enabled": settings.scheduler_enabled,
            "translate_available": bool(settings.google_translate_api_key),
            "storage_available": bool(settings.supabase_url and settings.supabase_service_role_key),
        }

        try:
            async with async_session() as session:
                await session.execute(text("SELECT 1"))
                result["database"] = "connected"

                # Get last completed scrape
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
        except Exception as e:
            result["status"] = "degraded"
            result["database"] = f"error: {str(e)[:100]}"

        return result

    # --- Remote trigger endpoint (K-05) ---
    @app.post("/api/scrape/trigger")
    async def remote_trigger(request: Request):
        """Remote trigger endpoint for the Next.js app to start scrape jobs.

        Requires X-API-Key header matching SCRAPER_API_KEY env var.
        """
        # Verify API key
        api_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
        if not settings.scraper_api_key:
            raise HTTPException(status_code=500, detail="SCRAPER_API_KEY not configured")
        if api_key != settings.scraper_api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")

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
