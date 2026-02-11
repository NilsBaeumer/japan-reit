from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting Japan REIT API", env=settings.app_env)
    # Auto-create tables on startup (idempotent — only creates missing tables)
    from app.database import create_all_tables
    import app.models  # noqa: F401 — ensure all models are registered
    await create_all_tables()
    logger.info("Database tables ready", backend="sqlite" if settings.is_sqlite else "postgresql")

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
        title="Japan Real Estate Investment Tool",
        description="Comprehensive tool for Japanese real estate market analysis",
        version="0.1.0",
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

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "version": "0.1.0"}

    return app


app = create_app()
