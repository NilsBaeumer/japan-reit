"""Scraper registry - maps source IDs to scraper classes."""

from typing import Any

from app.scrapers.base import AbstractScraper


_REGISTRY: dict[str, type[AbstractScraper]] = {}


def register_scraper(source_id: str):
    """Decorator to register a scraper class."""

    def decorator(cls: type[AbstractScraper]):
        _REGISTRY[source_id] = cls
        return cls

    return decorator


def get_scraper(source_id: str, config: dict[str, Any] | None = None) -> AbstractScraper:
    """Instantiate a scraper by source ID."""
    scraper_class = _REGISTRY.get(source_id)
    if scraper_class is None:
        raise ValueError(f"No scraper registered for source: {source_id}")
    return scraper_class(config=config)


def list_scrapers() -> list[str]:
    """List all registered scraper source IDs."""
    return list(_REGISTRY.keys())
