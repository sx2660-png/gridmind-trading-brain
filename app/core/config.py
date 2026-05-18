"""Application configuration loaded from environment variables."""

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class Settings(BaseModel):
    app_name: str = Field(default="trading-brain")
    app_env: str = Field(default="dev")
    debug: bool = Field(default=True)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_name=os.getenv("APP_NAME", "trading-brain"),
            app_env=os.getenv("APP_ENV", "dev"),
            debug=os.getenv("DEBUG", "true").lower() in ("1", "true", "yes"),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()


settings = get_settings()
