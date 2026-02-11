"""Celery tasks for scraping operations."""

import asyncio
from datetime import datetime, timezone

import structlog

from app.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(bind=True, max_retries=2, soft_time_limit=3600)
def run_scrape_job(self, job_id: str):
    """
    Execute a scraping job.

    1. Load ScrapeJob from DB
    2. Instantiate correct scraper via registry
    3. Run scraper with search params
    4. Save results to DB
    5. Trigger enrichment for new properties
    """
    asyncio.run(_run_scrape_job_async(self, job_id))


async def _run_scrape_job_async(task, job_id: str):
    from sqlalchemy import select

    from app.database import async_session
    from app.models.scraping import ScrapeJob, ScrapeSource
    from app.scrapers.base import SearchParams
    from app.scrapers.registry import get_scraper
    from app.services.property_service import PropertyService

    async with async_session() as session:
        # Load job
        result = await session.execute(select(ScrapeJob).where(ScrapeJob.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            logger.error("Job not found", job_id=job_id)
            return

        # Load source config
        source = await session.get(ScrapeSource, job.source_id)
        if not source:
            logger.error("Source not found", source_id=job.source_id)
            return

        # Update job status
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        job.celery_task_id = task.request.id
        await session.commit()

        try:
            # Build search params
            params = SearchParams(
                prefecture_code=job.prefecture_code,
                municipality_code=job.municipality_code,
                price_max=job.search_params.get("price_max", 15_000_000) if job.search_params else 15_000_000,
            )

            # Run scraper
            scraper = get_scraper(job.source_id, config=source.config)
            listings, scrape_result = await scraper.run(params)

            # Save results to DB
            property_service = PropertyService(session)
            new_count = 0
            updated_count = 0

            for raw_listing in listings:
                is_new = await property_service.upsert_from_listing(raw_listing)
                if is_new:
                    new_count += 1
                else:
                    updated_count += 1

            await session.commit()

            # Update job with results
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            job.listings_found = scrape_result.listings_found
            job.listings_new = new_count
            job.listings_updated = updated_count
            if scrape_result.errors:
                job.error_message = "; ".join(scrape_result.errors[:5])

            await session.commit()

            logger.info(
                "Scrape job completed",
                job_id=job_id,
                found=scrape_result.listings_found,
                new=new_count,
                updated=updated_count,
            )

        except Exception as e:
            job.status = "failed"
            job.completed_at = datetime.now(timezone.utc)
            job.error_message = str(e)[:500]
            await session.commit()
            logger.error("Scrape job failed", job_id=job_id, error=str(e))
            raise
