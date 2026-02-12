from collections.abc import AsyncGenerator

from sqlalchemy import MetaData, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)


class Base(DeclarativeBase):
    metadata = metadata


# Determine engine kwargs based on database type
_db_url = settings.effective_database_url
_engine_kwargs: dict = {
    "echo": settings.app_debug,
}

if _db_url.startswith("sqlite"):
    # SQLite dev mode - no pool size settings
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL / Supabase production mode
    # Supabase uses PgBouncer on port 6543 (transaction pooling mode).
    # asyncpg's prepared statement cache conflicts with PgBouncer, so we disable it.
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 5
    _engine_kwargs["connect_args"] = {"statement_cache_size": 0}
    _engine_kwargs["pool_pre_ping"] = True

engine = create_async_engine(_db_url, **_engine_kwargs)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_all_tables():
    """Create scraper infrastructure tables (scrape_sources, scrape_jobs, scrape_logs).

    NOTE: Property data tables (properties, property_listings, property_images, etc.)
    are managed by the Next.js app via Drizzle ORM migrations. The scraper only creates
    its own tables that are not in the Drizzle schema.
    """
    async with engine.begin() as conn:
        # Only create tables that belong to the scraper (not Drizzle-managed)
        from app.models.scraping import ScrapeSource, ScrapeJob, ScrapeLog
        tables = [
            ScrapeSource.__table__,
            ScrapeJob.__table__,
            ScrapeLog.__table__,
        ]
        for table in tables:
            await conn.run_sync(lambda sync_conn, t=table: t.create(sync_conn, checkfirst=True))
