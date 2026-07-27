import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import structlog
from redis.asyncio import Redis

from app.config import get_settings
from app.db import async_session_factory
from app.delivery import claim_stmt, deliver_one
from app.logging import configure
from app.models import Event
from app.ratelimit import acquire

log = structlog.get_logger()


async def _work_loop(client: httpx.AsyncClient, redis: Redis) -> None:
    settings = get_settings()
    while True:
        async with async_session_factory() as session:
            deliveries = (await session.scalars(claim_stmt(settings.claim_batch_size))).all()
            for d in deliveries:
                d.status = "delivering"
            for d in deliveries:
                event = await session.get(Event, d.event_id)
                if not await acquire(
                    redis, str(event.tenant_id),
                    settings.bucket_capacity, settings.bucket_refill_per_s,
                ):
                    d.status = "pending"
                    d.next_attempt_at = datetime.now(tz=UTC) + timedelta(seconds=1)
                    log.info("delivery.rate_deferred", tenant_id=str(event.tenant_id))
                    continue
                await deliver_one(session, d, client, settings.delivery_timeout_s)
            await session.commit()
        if not deliveries:
            await asyncio.sleep(0.5)


async def run(concurrency: int = 5) -> None:
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url)
    async with httpx.AsyncClient() as client:
        async with asyncio.TaskGroup() as tg:
            for _ in range(concurrency):
                tg.create_task(_work_loop(client, redis))


if __name__ == "__main__":
    configure(json_logs=True)
    settings = get_settings()
    asyncio.run(run(settings.worker_concurrency))