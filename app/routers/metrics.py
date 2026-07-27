from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session

router = APIRouter()

_QUEUE_SQL = text("SELECT status, count(*) FROM deliveries GROUP BY status")

_HOUR_SQL = text("""
    SELECT
      count(*)                                                   AS attempts,
      count(*) FILTER (WHERE status_code IS NULL
                          OR status_code NOT BETWEEN 200 AND 299) AS failed,
      percentile_cont(0.50) WITHIN GROUP (ORDER BY response_ms)  AS p50,
      percentile_cont(0.95) WITHIN GROUP (ORDER BY response_ms)  AS p95,
      percentile_cont(0.99) WITHIN GROUP (ORDER BY response_ms)  AS p99
    FROM delivery_attempts
    WHERE created_at >= now() - interval '1 hour'
""")

_DLQ_SQL = text("""
    SELECT
      count(*) FILTER (WHERE status = 'dead'
                         AND updated_at >= now() - interval '1 hour') AS newly_dead,
      count(*) FILTER (WHERE created_at >= now() - interval '1 hour') AS created
    FROM deliveries
""")


@router.get("/metrics")
async def metrics(session: AsyncSession = Depends(get_session)) -> dict:
    queue = {status: n for status, n in (await session.execute(_QUEUE_SQL)).all()}
    hour = (await session.execute(_HOUR_SQL)).one()
    dlq = (await session.execute(_DLQ_SQL)).one()
    attempts = hour.attempts or 0
    return {
        "queue": {s: queue.get(s, 0) for s in ("pending", "delivering", "succeeded", "dead")},
        "last_hour": {
            "attempts": attempts,
            "retry_rate": round(hour.failed / attempts, 4) if attempts else 0.0,
            "dlq_rate": round(dlq.newly_dead / dlq.created, 4) if dlq.created else 0.0,
            "latency_ms": {
                "p50": round(float(hour.p50 or 0), 1),
                "p95": round(float(hour.p95 or 0), 1),
                "p99": round(float(hour.p99 or 0), 1),
            },
        },
    }
