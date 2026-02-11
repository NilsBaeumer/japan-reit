import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Database — Supabase PostgreSQL (primary) or SQLite (local dev fallback)
    database_url: str = ""  # Supabase connection string (postgresql://...)
    use_sqlite: bool = False  # Set True for local dev without Supabase

    # Legacy PostgreSQL settings (only used if database_url not set and use_sqlite=False)
    postgres_user: str = "japan_reit"
    postgres_password: str = "japan_reit_dev"
    postgres_db: str = "japan_reit"
    db_host: str = "localhost"
    db_port: int = 5432

    @property
    def effective_database_url(self) -> str:
        """Return the async database URL to use."""
        if self.database_url:
            url = self.database_url
            # Convert postgres:// to postgresql+asyncpg://
            if url.startswith("postgres://"):
                url = "postgresql+asyncpg://" + url[len("postgres://"):]
            elif url.startswith("postgresql://"):
                url = "postgresql+asyncpg://" + url[len("postgresql://"):]
            elif not url.startswith("postgresql+asyncpg://"):
                url = "postgresql+asyncpg://" + url
            return url
        if self.use_sqlite:
            db_path = Path(__file__).parent.parent / "data" / "japan_reit.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite+aiosqlite:///{db_path}"
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.db_host}:{self.db_port}/{self.postgres_db}"
        )

    @property
    def is_sqlite(self) -> bool:
        return self.effective_database_url.startswith("sqlite")

    # API key for securing remote trigger endpoint
    scraper_api_key: str = ""

    # Supabase Storage (for image uploads)
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = "property-images"

    # Google Translate
    google_translate_api_key: str = ""

    # Redis (optional, for Celery)
    redis_host: str = "localhost"
    redis_port: int = 6379

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    # MLIT reinfolib API
    reinfolib_api_key: str = ""

    # Scraping
    scrape_default_delay: float = 3.0
    scrape_max_retries: int = 3

    # Scheduler (periodic scraping)
    scheduler_enabled: bool = False
    scheduler_interval_hours: float = 6.0


settings = Settings()
