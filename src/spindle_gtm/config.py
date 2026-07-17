"""Runtime configuration loaded from environment / .env (never committed)."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Environment-backed settings. Secrets live only in .env (gitignored)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    db_path: Path = Field(default=Path("db/spindle.db"), alias="SPINDLE_DB_PATH")
    apollo_api_key: str = Field(default="", alias="APOLLO_API_KEY")
    apollo_seed_list_id: str = Field(default="", alias="APOLLO_SEED_LIST_ID")

    sender_name: str = Field(default="", alias="SENDER_NAME")
    sender_company: str = Field(default="", alias="SENDER_COMPANY")
    sender_postal_address: str = Field(default="", alias="SENDER_POSTAL_ADDRESS")
    unsubscribe_url: str = Field(default="", alias="UNSUBSCRIBE_URL")

    @property
    def region_policy_path(self) -> Path:
        return REPO_ROOT / "config" / "region_policy.toml"


def get_settings() -> Settings:
    return Settings()
