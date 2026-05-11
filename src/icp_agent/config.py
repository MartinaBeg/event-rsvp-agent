"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Container for all runtime config. Reads env vars (and `.env` locally)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Apify
    apify_token: str = Field(default="", description="Apify API token.")
    apify_actor_id: str = Field(default="2SyF0bVxmgGr8IVCZ")
    apify_batch_size: int = Field(default=25, ge=1, le=100)

    # Local Excel workbook
    excel_path: str = Field(
        default="rsvp.xlsx",
        description="Path to the .xlsx workbook to read/write.",
    )
    excel_tab: str = Field(default="RSVP List", description="Worksheet/tab name.")

    # Pipeline tuning
    approval_cap: int = Field(default=75, ge=0)
    dry_run: bool = Field(default=False)

    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="console")

    @field_validator("log_format")
    @classmethod
    def _validate_log_format(cls, v: str) -> str:
        v = v.lower()
        if v not in {"console", "json"}:
            raise ValueError("LOG_FORMAT must be 'console' or 'json'")
        return v

    def resolved_excel_path(self) -> Path:
        return Path(self.excel_path).expanduser().resolve()


def load_settings() -> Settings:
    """Read settings from env. Raises validation errors loudly."""
    return Settings()
