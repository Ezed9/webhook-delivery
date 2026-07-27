import uuid


from app.db import async_session_factory
from app.models import Delivery, DeliveryAttempt, Endpoint, Event, Tenant


async def test_metrics_empty_db(client) -> None:
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["queue"]["pending"] == 0
    assert data["last_hour"]["attempts"] == 0
    assert data["last_hour"]["retry_rate"] == 0.0


async def test_metrics_with_data(client) -> None:
    async with async_session_factory() as s:
        t = Tenant(name="t", api_key_hash="m_" + str(uuid.uuid4()))
        s.add(t)
        await s.flush()
        ep = Endpoint(tenant_id=t.id, url="https://x.com", secret="s")
        s.add(ep)
        await s.flush()
        ev = Event(
            tenant_id=t.id, endpoint_id=ep.id, event_type="x",
            payload={}, idempotency_key=str(uuid.uuid4()),
        )
        s.add(ev)
        await s.flush()
        d = Delivery(event_id=ev.id, endpoint_id=ep.id, status="succeeded")
        s.add(d)
        await s.flush()
        for i, ms in enumerate([10, 20, 30, 40, 50], 1):
            s.add(DeliveryAttempt(
                delivery_id=d.id, attempt_number=i, status_code=200, response_ms=ms,
            ))
        await s.commit()

    resp = await client.get("/metrics")
    data = resp.json()
    assert data["queue"]["succeeded"] == 1
    assert data["last_hour"]["attempts"] == 5
    assert data["last_hour"]["latency_ms"]["p50"] == 30.0
