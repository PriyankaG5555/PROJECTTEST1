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
    google_places_api_key: str | None = None
    # AI day planning (specs/ai-feature.md). No provider configured -> 503 AI_PLANNING_UNAVAILABLE.
    ai_llm_provider: Literal["anthropic"] | None = None
    ai_llm_api_key: str | None = None
    ai_llm_model: str = "claude-opus-5-5"
    ai_location_provider: Literal["google_places"] | None = "google_places"
    ai_plan_daily_limit: int = Field(default=10, ge=1)

    @property
    def bcrypt_rounds(self) -> int:
        # Cost 12 in real use (backend-spec §1); cheap hashing keeps the test suite fast.
        return 4 if self.environment == "test" else 12


@lru_cache
def get_settings() -> Settings:
    return Settings()
