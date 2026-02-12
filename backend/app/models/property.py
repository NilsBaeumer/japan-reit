"""Property models — aliases to the Drizzle-compatible schema.

The actual table definitions live in new_schema.py which matches the
Drizzle ORM schema used by the Next.js frontend. These aliases maintain
backward compatibility for API endpoints that import from this module.
"""

from app.models.new_schema import (
    NewProperty as Property,
    NewPropertyListing as PropertyListing,
    NewPropertyImage as PropertyImage,
)

__all__ = ["Property", "PropertyListing", "PropertyImage"]
