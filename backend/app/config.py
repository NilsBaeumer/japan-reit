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

    # Database - supports PostgreSQL (production) or SQLite (dev fallback)
    database_url_override: str = ""  # Set to override auto-detection
    postgres_user: str = "japan_reit"
    postgres_password: str = "japan_reit_dev"
    postgres_db: str = "japan_reit"
    db_host: str = "localhost"
    db_port: int = 5432
    use_sqlite: bool = True  # Default to SQLite for easy dev setup

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        if self.use_sqlite:
            db_path = Path(__file__).parent.parent / "data" / "japan_reit.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite+aiosqlite:///{db_path}"
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.db_host}:{self.db_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        if self.use_sqlite:
            db_path = Path(__file__).parent.parent / "data" / "japan_reit.db"
            return f"sqlite:///{db_path}"
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.db_host}:{self.db_port}/{self.postgres_db}"
        )

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    # Redis
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
    scheduler_enabled: bool = False  # Set True to auto-scrape on interval
    scheduler_interval_hours: float = 6.0


settings = Settings()
