import uuid

from httpx import AsyncClient

from app.db import async_session_factory
from app.models import Delivery, Endpoint, Event, Tenant


async def _create_dead_delivery() -> tuple[str, str]:
    async with async_session_factory() as s:
        t = Tenant(name="t", api_key_hash="dlq_" + str(uuid.uuid4()))
        s.add(t)
        await s.flush()
        ep = Endpoint(tenant_id=t.id, url="https://dead.com", secret="s")
        s.add(ep)
        await s.flush()
        ev = Event(
            tenant_id=t.id, endpoint_id=ep.id, event_type="x",
            payload={}, idempotency_key=str(uuid.uuid4()),
        )
        s.add(ev)
        await s.flush()
        d = Delivery(
            event_id=ev.id, endpoint_id=ep.id, status="dead", attempt_count=8,
        )
        s.add(d)
        await s.commit()
        return str(d.id), t.api_key_hash


async def test_retry_revives_dead(client: AsyncClient) -> None:
    from app.auth import generate_api_key

    async with async_session_factory() as s:
        plaintext, key_hash = generate_api_key()
        t = Tenant(name="t", api_key_hash=key_hash)
        s.add(t)
        await s.flush()
        ep = Endpoint(tenant_id=t.id, url="https://dead.com", secret="s")
        s.add(ep)
        await s.flush()
        ev = Event(
            tenant_id=t.id, endpoint_id=ep.id, event_type="x",
            payload={}, idempotency_key=str(uuid.uuid4()),
        )
        s.add(ev)
        await s.flush()
        d = Delivery(event_id=ev.id, endpoint_id=ep.id, status="dead", attempt_count=8)
        s.add(d)
        await s.commit()
        delivery_id = str(d.id)

    headers = {"Authorization": f"Bearer {plaintext}"}
    resp = await client.post(f"/deliveries/{delivery_id}/retry", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


async def test_retry_non_dead_409(client: AsyncClient) -> None:
    from app.auth import generate_api_key

    async with async_session_factory() as s:
        plaintext, key_hash = generate_api_key()
        t = Tenant(name="t", api_key_hash=key_hash)
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
        d = Delivery(event_id=ev.id, endpoint_id=ep.id, status="pending")
        s.add(d)
        await s.commit()
        delivery_id = str(d.id)

    headers = {"Authorization": f"Bearer {plaintext}"}
    resp = await client.post(f"/deliveries/{delivery_id}/retry", headers=headers)
    assert resp.status_code == 409
