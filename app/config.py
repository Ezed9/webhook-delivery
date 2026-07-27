from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/webhooks"
    redis_url: str = "redis://localhost:6379/0"
    worker_concurrency: int = 5
    claim_batch_size: int = 10
    delivery_timeout_s: float = 10.0
    max_attempts: int = 8
    backoff_base_s: float = 5.0
    backoff_cap_s: float = 900.0
    bucket_capacity: int = 10
    bucket_refill_per_s: float = 5.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
