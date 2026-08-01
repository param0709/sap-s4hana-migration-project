"""Application configuration loaded from environment variables."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. Every value can be overridden by an environment variable."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Application ---
    app_name: str = "SAP S/4HANA Migration Co-Pilot"
    app_env: str = "local"
    api_prefix: str = "/api/v1"

    # --- Database ---
    database_url: str = (
        "postgresql+psycopg://copilot:copilot@localhost:5432/migration_copilot"
    )

    # --- File storage ---
    storage_dir: str = "storage"
    max_upload_mb: int = 25

    # --- CORS ---
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
