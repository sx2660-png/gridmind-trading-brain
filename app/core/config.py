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
    policy_articles_dir: str = Field(default="articles")
    policy_index_path: str = Field(default="data/processed/policy_index.json")
    llm_api_key: str = Field(default="")
    llm_base_url: str = Field(default="https://api.openai.com/v1")
    llm_model: str = Field(default="gpt-4o-mini")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_name=os.getenv("APP_NAME", "trading-brain"),
            app_env=os.getenv("APP_ENV", "dev"),
            debug=os.getenv("DEBUG", "true").lower() in ("1", "true", "yes"),
            policy_articles_dir=os.getenv("POLICY_ARTICLES_DIR", "articles"),
            policy_index_path=os.getenv("POLICY_INDEX_PATH", "data/processed/policy_index.json"),
            llm_api_key=os.getenv("LLM_API_KEY", ""),
            llm_base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
            llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()


settings = get_settings()
