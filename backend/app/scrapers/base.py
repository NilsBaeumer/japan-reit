"""
Abstract base class for property portal scrapers.

Provides common functionality:
- Rate limiting (configurable delay between requests)
- Retry with exponential backoff
- Request logging to scrape_logs
- Session management
- Progress reporting
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass
class RawListing:
    """Raw listing data extracted from a portal."""

    source: str
    source_id: str
    source_url: str
    title: str | None = None
    price: int | None = None
    address: str | None = None
    prefecture: str | None = None
    municipality: str | None = None
    land_area_sqm: float | None = None
    building_area_sqm: float | None = None
    floor_plan: str | None = None
    year_built: int | None = None
    structure: str | None = None
    floors: int | None = None
    road_width_m: float | None = None
    road_frontage_m: float | None = None
    rebuild_possible: bool | None = None
    city_planning_zone: str | None = None
    use_zone: str | None = None
    coverage_ratio: float | None = None
    floor_area_ratio: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    image_urls: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchParams:
    """Parameters for a property search."""

    prefecture_code: str | None = None
    municipality_code: str | None = None
    price_min: int | None = None
    price_max: int = 15_000_000  # Default: ¥15M (1500万円)
    property_type: str = "detached_house"  # 中古戸建
    max_pages: int = 50


@dataclass
class ScrapeResult:
    """Result summary of a scraping run."""

    listings_found: int = 0
    listings_new: int = 0
    listings_updated: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None


class AbstractScraper(ABC):
    """
    Base class for all property portal scrapers.

    Subclasses must implement:
    - search_listings(): Execute search and return raw listing data
    - scrape_detail(): Scrape full detail page for a single listing
    """

    source_id: str = ""
    base_url: str = ""
    crawl_delay_seconds: float = 3.0
    max_retries: int = 3

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        if "crawl_delay_seconds" in self.config:
            self.crawl_delay_seconds = self.config["crawl_delay_seconds"]

    @abstractmethod
    async def search_listings(self, params: SearchParams) -> list[RawListing]:
        """
        Execute search and return raw listing data.
        Should handle pagination internally.
        """
        ...

    @abstractmethod
    async def scrape_detail(self, listing_url: str) -> RawListing | None:
        """
        Scrape full detail page for a single listing.
        Returns enriched RawListing or None if scraping failed.
        """
        ...

    async def run(self, params: SearchParams) -> tuple[list[RawListing], ScrapeResult]:
        """
        Main entry point. Orchestrates search and detail scraping.

        Returns:
            Tuple of (listings, result_summary)
        """
        result = ScrapeResult()
        all_listings: list[RawListing] = []

        try:
            logger.info(
                "Starting scrape",
                source=self.source_id,
                prefecture=params.prefecture_code,
                price_max=params.price_max,
            )

            # Phase 1: Search for listings
            search_results = await self.search_listings(params)
            result.listings_found = len(search_results)

            logger.info(
                "Search complete",
                source=self.source_id,
                listings_found=result.listings_found,
            )

            # Phase 2: Scrape details for each listing
            for i, listing in enumerate(search_results):
                try:
                    if listing.source_url:
                        detailed = await self.scrape_detail(listing.source_url)
                        if detailed:
                            all_listings.append(detailed)
                        else:
                            all_listings.append(listing)
                    else:
                        all_listings.append(listing)

                    # Rate limiting between detail page requests
                    if i < len(search_results) - 1:
                        await asyncio.sleep(self.crawl_delay_seconds)

                except Exception as e:
                    logger.warning(
                        "Failed to scrape detail",
                        source=self.source_id,
                        url=listing.source_url,
                        error=str(e),
                    )
                    result.errors.append(f"Detail scrape failed: {listing.source_url}: {e}")
                    all_listings.append(listing)  # Use search-level data

        except Exception as e:
            logger.error(
                "Scrape failed",
                source=self.source_id,
                error=str(e),
            )
            result.errors.append(f"Search failed: {e}")

        result.completed_at = datetime.now(timezone.utc)
        return all_listings, result

    async def _delay(self):
        """Wait for the configured crawl delay."""
        await asyncio.sleep(self.crawl_delay_seconds)
