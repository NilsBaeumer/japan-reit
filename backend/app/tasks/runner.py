"""Async background task runner (dev mode - no Celery/Redis required).

Includes:
- dispatch_scrape_job(): Run a scrape job as a background asyncio task
- start_scheduler(): Periodic scheduler that auto-dispatches scrape jobs
"""
import asyncio
from datetime import datetime, timezone

import structlog

logger = structlog.get_logger()

# Track running tasks
_running_tasks: dict[str, asyncio.Task] = {}
_scheduler_task: asyncio.Task | None = None


async def run_scrape_job_async(job_id: str):
    """Run a scraping job as an async background task.

    Uses the new SupabasePropertyService to write to the Drizzle-compatible schema,
    with optional Google Translate and Supabase Storage image upload.
    """
    from sqlalchemy import select
    from app.database import async_session
    from app.models.scraping import ScrapeJob, ScrapeSource
    from app.scrapers.base import SearchParams
    from app.scrapers.registry import get_scraper
    from app.services.supabase_property_service import SupabasePropertyService
    from app.services.translate_service import TranslateService
    from app.services.image_upload_service import ImageUploadService

    async with async_session() as session:
        result = await session.execute(select(ScrapeJob).where(ScrapeJob.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            logger.error("Job not found", job_id=job_id)
            return

        source = await session.get(ScrapeSource, job.source_id)
        if not source:
            logger.error("Source not found", source_id=job.source_id)
            return

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        await session.commit()

        # Initialize optional services (set to None first for finally-block safety)
        translate_service = None
        image_service = None

        try:
            translate_service = TranslateService()
            image_service = ImageUploadService()
            params = SearchParams(
                prefecture_code=job.prefecture_code,
                municipality_code=job.municipality_code,
                price_max=job.search_params.get("price_max", 15_000_000) if job.search_params else 15_000_000,
            )

            scraper = get_scraper(job.source_id, config=source.config)
            listings, scrape_result = await scraper.run(params)

            property_service = SupabasePropertyService(
                session,
                translate_service=translate_service if translate_service.is_available else None,
                image_service=image_service if image_service.is_available else None,
            )
            new_count = 0
            updated_count = 0
            batch_size = 25  # Commit every N listings to avoid losing progress

            for i, raw_listing in enumerate(listings):
                try:
                    # Use a savepoint so one failure doesn't kill the whole batch
                    async with session.begin_nested():
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

                # Commit in batches to persist progress incrementally
                if (i + 1) % batch_size == 0:
                    await session.commit()
                    logger.info("Batch committed", processed=i + 1, new=new_count, updated=updated_count)

            await session.commit()

            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            job.listings_found = scrape_result.listings_found
            job.listings_new = new_count
            job.listings_updated = updated_count
            if scrape_result.errors:
                job.error_message = "; ".join(scrape_result.errors[:5])
            await session.commit()

            logger.info("Scrape job completed", job_id=job_id, found=scrape_result.listings_found, new=new_count, updated=updated_count)

        except Exception as e:
            job.status = "failed"
            job.completed_at = datetime.now(timezone.utc)
            job.error_message = str(e)[:500]
            await session.commit()
            logger.error("Scrape job failed", job_id=job_id, error=str(e))

        finally:
            if translate_service:
                await translate_service.close()
            if image_service:
                await image_service.close()


def dispatch_scrape_job(job_id: str):
    """Dispatch a scrape job as a background asyncio task."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        task = loop.create_task(run_scrape_job_async(job_id))
        _running_tasks[job_id] = task
        task.add_done_callback(lambda t: _running_tasks.pop(job_id, None))
        logger.info("Dispatched scrape job (async)", job_id=job_id)
    else:
        asyncio.run(run_scrape_job_async(job_id))
        logger.info("Ran scrape job (sync)", job_id=job_id)


def get_task_status(job_id: str) -> str | None:
    """Check if a task is still running."""
    task = _running_tasks.get(job_id)
    if task is None:
        return None
    if task.done():
        return "done"
    return "running"


# ---------------------------------------------------------------------------
# Scheduled scraping (replaces Celery Beat)
# ---------------------------------------------------------------------------

async def _scheduler_loop(interval_hours: float = 6.0):
    """Periodically create scrape jobs for all enabled sources."""
    from sqlalchemy import select
    from app.database import async_session
    from app.models.scraping import ScrapeSource, ScrapeJob

    interval_seconds = interval_hours * 3600
    logger.info("Scheduler started", interval_hours=interval_hours)

    while True:
        try:
            await asyncio.sleep(interval_seconds)
            logger.info("Scheduler tick — checking for due scrape sources")

            async with async_session() as session:
                result = await session.execute(
                    select(ScrapeSource).where(ScrapeSource.is_enabled.is_(True))
                )
                sources = result.scalars().all()

                for source in sources:
                    existing = await session.execute(
                        select(ScrapeJob).where(
                            ScrapeJob.source_id == source.id,
                            ScrapeJob.status.in_(["pending", "running"]),
                        )
                    )
                    if existing.scalar_one_or_none():
                        logger.debug("Skipping — job already active", source=source.id)
                        continue

                    last_job_q = await session.execute(
                        select(ScrapeJob)
                        .where(
                            ScrapeJob.source_id == source.id,
                            ScrapeJob.status == "completed",
                        )
                        .order_by(ScrapeJob.completed_at.desc())
                        .limit(1)
                    )
                    last_job = last_job_q.scalar_one_or_none()

                    if last_job and last_job.completed_at:
                        elapsed = (datetime.now(timezone.utc) - last_job.completed_at).total_seconds()
                        if elapsed < interval_seconds:
                            logger.debug(
                                "Skipping — recently scraped",
                                source=source.id,
                                elapsed_h=round(elapsed / 3600, 1),
                            )
                            continue

                    job = ScrapeJob(
                        source_id=source.id,
                        status="pending",
                        search_params=source.config.get("default_params", {}) if source.config else {},
                    )
                    session.add(job)
                    await session.flush()

                    job_id = str(job.id)
                    await session.commit()

                    dispatch_scrape_job(job_id)
                    logger.info("Scheduler dispatched scrape job", source=source.id, job_id=job_id)

        except asyncio.CancelledError:
            logger.info("Scheduler cancelled")
            break
        except Exception as e:
            logger.error("Scheduler error", error=str(e))
            await asyncio.sleep(60)


def start_scheduler(interval_hours: float = 6.0):
    """Start the periodic scraping scheduler as a background task."""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        logger.warning("Scheduler already running")
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("No running event loop — scheduler not started")
        return

    _scheduler_task = loop.create_task(_scheduler_loop(interval_hours))
    logger.info("Scheduler task created", interval_hours=interval_hours)


def stop_scheduler():
    """Stop the periodic scraping scheduler."""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        logger.info("Scheduler stop requested")
    _scheduler_task = None
