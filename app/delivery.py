import json
import time
from datetime import UTC, datetime, timedelta

import httpx
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.backoff import next_delay_s
from app.config import get_settings
from app.models import Delivery, DeliveryAttempt, Endpoint, Event
from app.signing import sign

log = structlog.get_logger()


def claim_stmt(batch_size: int):
    return (
        select(Delivery)
        .where(Delivery.status == "pending", Delivery.next_attempt_at <= func.now())
        .order_by(Delivery.next_attempt_at)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )


async def deliver_one(
    session: AsyncSession, delivery: Delivery, client: httpx.AsyncClient, timeout_s: float
) -> None:
    event = await session.get(Event, delivery.event_id)
    endpoint = await session.get(Endpoint, delivery.endpoint_id)
    body = json.dumps(
        {"event_id": str(event.id), "event_type": event.event_type, "payload": event.payload},
        separators=(",", ":"),
    ).encode()

    timestamp = str(int(time.time()))
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": f"v1={sign(endpoint.secret, timestamp, body)}",
        "X-Webhook-Timestamp": timestamp,
        "X-Webhook-Event-Id": str(event.id),
    }

    attempt_number = delivery.attempt_count + 1
    start = time.monotonic()
    try:
        resp = await client.post(
            endpoint.url, content=body, headers=headers, timeout=timeout_s,
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        session.add(
            DeliveryAttempt(
                delivery_id=delivery.id,
                attempt_number=attempt_number,
                status_code=resp.status_code,
                response_ms=elapsed_ms,
            )
        )
        if 200 <= resp.status_code < 300:
            delivery.status = "succeeded"
            delivery.last_status_code = resp.status_code
            structlog.contextvars.bind_contextvars(delivery_id=str(delivery.id))
            log.info(
                "delivery.succeeded",
                attempt=attempt_number,
                status_code=resp.status_code,
                tenant_id=str(event.tenant_id),
            )
            return
        _handle_failure(delivery, status_code=resp.status_code, error=None)
    except httpx.HTTPError as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        session.add(
            DeliveryAttempt(
                delivery_id=delivery.id,
                attempt_number=attempt_number,
                error=str(exc),
                response_ms=elapsed_ms,
            )
        )
        _handle_failure(delivery, status_code=None, error=str(exc))


def _handle_failure(delivery: Delivery, status_code: int | None, error: str | None) -> None:
    settings = get_settings()
    delivery.attempt_count += 1
    delivery.last_status_code = status_code
    delivery.last_error = error
    if delivery.attempt_count >= settings.max_attempts:
        delivery.status = "dead"
        log.warning(
            "delivery.dead",
            delivery_id=str(delivery.id),
            attempts=delivery.attempt_count,
        )
    else:
        delay = next_delay_s(delivery.attempt_count, settings.backoff_base_s, settings.backoff_cap_s)
        delivery.status = "pending"
        delivery.next_attempt_at = datetime.now(tz=UTC) + timedelta(seconds=delay)
        log.info(
            "delivery.retry",
            delivery_id=str(delivery.id),
            attempt=delivery.attempt_count,
            next_in_s=round(delay, 1),
        )
