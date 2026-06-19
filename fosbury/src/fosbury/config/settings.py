"""Application settings via pydantic-settings.

All configuration is read from environment variables or a ``.env`` file in the
working directory.  Import :class:`Settings` and instantiate it once at startup;
pass it by dependency injection to extractors, loaders, etc.

Example::

    from fosbury.config.settings import Settings
    settings = Settings()          # reads .env automatically
    print(settings.stub_mode)      # True / False
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the Fosbury pipeline.

    All fields can be overridden by environment variables of the same name
    (uppercased).  A ``.env`` file in the working directory is loaded
    automatically.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # -- API credentials --------------------------------------------------
    eia_api_key: str = Field(
        default="",
        description="EIA open-data API key (https://www.eia.gov/opendata/). "
        "Required when stub_mode=false and pjm_eia source is enabled.",
    )
    pjm_api_key: str = Field(
        default="",
        description="PJM Data Miner subscription key. Leave blank to use public endpoints only.",
    )

    # -- Behaviour --------------------------------------------------------
    stub_mode: bool = Field(
        default=True,
        description="When True, extractors serve fixture JSON instead of hitting live APIs.",
    )
    log_level: str = Field(default="INFO")
    lookback_days: int = Field(default=7, ge=1, le=365)

    # -- Storage ----------------------------------------------------------
    sqlite_path: Path = Field(default=Path("data/sqlite/fosbury.db"))
    parquet_dir: Path = Field(default=Path("data/parquet"))

    # -- HTTP retry -------------------------------------------------------
    http_retry_max: int = Field(default=3, ge=1, le=10)
    http_retry_wait_seconds: float = Field(default=2.0, ge=0.5)
    http_timeout_seconds: float = Field(default=30.0, ge=1.0)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return upper

    def ensure_storage_dirs(self) -> None:
        """Create storage directories if they don't exist."""
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.parquet_dir.mkdir(parents=True, exist_ok=True)
