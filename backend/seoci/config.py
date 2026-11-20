from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./data/seoci.db"
    llm_model: str = ""
    serp_provider: str = "mock"
    dataforseo_login: str = ""
    dataforseo_password: str = ""
    max_revision_cycles: int = 2
    run_budget_usd: float = 2.0
    cache_ttl_seconds: int = 3600
    network_timeout: float = 20
    worker_poll_seconds: float = 0.5


settings = Settings()
