"""Application settings, loaded from environment variables (see backend-spec.md §8)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str
    jwt_secret: str = Field(min_length=32)
    environment: Literal["development", "test", "production"] = "development"
    session_ttl_days: int = Field(default=7, ge=1)
    cookie_secure: bool = True
    log_level: str = "INFO"

    @property
    def bcrypt_rounds(self) -> int:
        # Cost 12 in real use (backend-spec §1); cheap hashing keeps the test suite fast.
        return 4 if self.environment == "test" else 12


@lru_cache
def get_settings() -> Settings:
    return Settings()
