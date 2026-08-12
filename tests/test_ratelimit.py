import pytest
from app.ratelimit import acquire
from redis.asyncio import Redis

pytestmark = pytest.mark.asyncio

async def test_ratelimit() -> None:
    pass
