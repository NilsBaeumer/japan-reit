"""Seed reference data into the database."""

import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.location import Prefecture
from app.models.scraping import ScrapeSource
from app.seed.prefectures import PREFECTURES
from app.seed.scrape_sources import SCRAPE_SOURCES


async def seed_prefectures(session: AsyncSession) -> int:
    """Seed 47 prefectures."""
    count = 0
    for data in PREFECTURES:
        existing = await session.get(Prefecture, data["code"])
        if existing is None:
            session.add(Prefecture(**data))
            count += 1
    await session.commit()
    return count


async def seed_scrape_sources(session: AsyncSession) -> int:
    """Seed scraping source configurations."""
    count = 0
    for data in SCRAPE_SOURCES:
        existing = await session.get(ScrapeSource, data["id"])
        if existing is None:
            session.add(ScrapeSource(**data))
            count += 1
    await session.commit()
    return count


async def run_all_seeds():
    """Run all seed operations."""
    async with async_session() as session:
        prefectures_added = await seed_prefectures(session)
        print(f"Prefectures: {prefectures_added} added")

        sources_added = await seed_scrape_sources(session)
        print(f"Scrape sources: {sources_added} added")

    print("Seeding complete.")


if __name__ == "__main__":
    asyncio.run(run_all_seeds())
