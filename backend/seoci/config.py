from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./data/seoci.db"
    llm_model: str = ""
    llm_api_base: str = ""
    llm_api_key: str = ""
    serp_provider: Literal["mock", "dataforseo"] = "mock"
    dataforseo_login: str = ""
    dataforseo_password: str = ""
    max_revision_cycles: int = 2
    run_budget_usd: float = 2.0
    cache_ttl_seconds: int = 3600
    network_timeout: float = 20
    worker_poll_seconds: float = 0.5
    github_token: str = ""
    github_api_url: str = "https://api.github.com"
    auth_users_file: str = "./data/auth-users"
    auth_secret: str = ""


settings = Settings()
