"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All application settings sourced strictly from environment variables.

    No business constants or URLs are hardcoded here.
    Runtime-configurable values (upload limits, cutoffs) live in the
    SETTING database table and are fetched via SettingService.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Database ---
    database_url: str

    # --- Auth ---
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 120
    refresh_token_expire_days: int = 7

    # --- Application ---
    environment: str = "development"
    log_level: str = "INFO"
    allowed_origins: list[str] = ["http://localhost:5173"]

    @property
    def is_production(self) -> bool:
        """Return True if running in a production environment."""
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()  # type: ignore[call-arg]
