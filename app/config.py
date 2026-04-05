from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    serpapi_key: str = ""

    menuchat_backend_url: str = ""
    crm_api_key: str = ""
    smartlead_api_key: str = ""

    postgres_url: str = "postgresql://agent:agent_dev_password@localhost:5432/agent_state"
    qdrant_url: str = "http://localhost:6333"

    host: str = "0.0.0.0"
    port: int = 8100
    log_level: str = "info"

    model_strategist: str = "claude-opus-4-20250514"
    model_writer: str = "claude-sonnet-4-20250514"
    model_reviewer: str = "claude-haiku-4-5-20251001"
    model_router: str = "claude-haiku-4-5-20251001"
    model_critic: str = "claude-sonnet-4-20250514"

    strategist_thinking_budget: int = 10000
    strategist_max_tokens: int = 16000
    writer_max_tokens: int = 4000
    reviewer_max_tokens: int = 1000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
