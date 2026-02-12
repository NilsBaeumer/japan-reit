"""Celery tasks for scraping operations.

NOTE: This module is the Celery-based version of runner.py. In production
we use the async runner (runner.py) which doesn't require Celery/Redis.
This module is kept for compatibility but uses the same SupabasePropertyService
as the async runner.
"""

import asyncio
from datetime import datetime, timezone

import structlog

from app.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(bind=True, max_retries=2, soft_time_limit=3600)
def run_scrape_job(self, job_id: str):
    """
    Execute a scraping job via Celery.

    Uses the same SupabasePropertyService as the async runner to write
    to the Drizzle-compatible schema.
    """
    asyncio.run(_run_scrape_job_async(self, job_id))


async def _run_scrape_job_async(task, job_id: str):
    from sqlalchemy import select

    from app.database import async_session
    from app.models.scraping import ScrapeJob, ScrapeSource
    from app.scrapers.base import SearchParams
    from app.scrapers.registry import get_scraper
    from app.services.supabase_property_service import SupabasePropertyService
    from app.services.translate_service import TranslateService
    from app.services.image_upload_service import ImageUploadService

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

        translate_service = None
        image_service = None

        try:
            translate_service = TranslateService()
            image_service = ImageUploadService()

            # Build search params
            params = SearchParams(
                prefecture_code=job.prefecture_code,
                municipality_code=job.municipality_code,
                price_max=job.search_params.get("price_max", 15_000_000) if job.search_params else 15_000_000,
            )

            # Run scraper
            scraper = get_scraper(job.source_id, config=source.config)
            listings, scrape_result = await scraper.run(params)

            # Save results to DB using new schema
            property_service = SupabasePropertyService(
                session,
                translate_service=translate_service if translate_service.is_available else None,
                image_service=image_service if image_service.is_available else None,
            )
            new_count = 0
            updated_count = 0

            for raw_listing in listings:
                try:
                    is_new = await property_service.upsert_from_listing(raw_listing)
                    if is_new:
                        new_count += 1
                    else:
                        updated_count += 1
                except Exception as e:
                    logger.warning(
                        "Failed to upsert listing",
                        source=raw_listing.source,
                        source_id=raw_listing.source_id,
                        error=str(e),
                    )
                    scrape_result.errors.append(f"Upsert failed: {raw_listing.source_id}: {e}")

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

        finally:
            if translate_service:
                await translate_service.close()
            if image_service:
                await image_service.close()
