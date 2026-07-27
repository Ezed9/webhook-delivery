import uuid

from httpx import AsyncClient
from sqlalchemy import text

from app.db import async_session_factory


async def test_outbox_creates_delivery(
    client: AsyncClient, auth_headers: dict, endpoint_id: str
) -> None:
    resp = await client.post(
        "/events",
        json={"endpoint_id": endpoint_id, "event_type": "test", "payload": {"k": 1}},
        headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert resp.status_code == 202
    async with async_session_factory() as s:
        row = (await s.execute(text("SELECT status FROM deliveries"))).one()
        assert row.status == "pending"


async def test_replay_no_extra_delivery(
    client: AsyncClient, auth_headers: dict, endpoint_id: str
) -> None:
    h = {**auth_headers, "Idempotency-Key": "outbox-dup"}
    body = {"endpoint_id": endpoint_id, "event_type": "test", "payload": {}}
    await client.post("/events", json=body, headers=h)
    await client.post("/events", json=body, headers=h)
    async with async_session_factory() as s:
        count = (await s.execute(text("SELECT count(*) FROM deliveries"))).scalar()
        assert count == 1


async def test_atomicity(
    client: AsyncClient, auth_headers: dict, endpoint_id: str, monkeypatch
) -> None:
    async def bad_enqueue(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.routers.events.enqueue", bad_enqueue)
    resp = await client.post(
        "/events",
        json={"endpoint_id": endpoint_id, "event_type": "test", "payload": {}},
        headers={**auth_headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert resp.status_code == 500
    async with async_session_factory() as s:
        events = (await s.execute(text("SELECT count(*) FROM events"))).scalar()
        deliveries = (await s.execute(text("SELECT count(*) FROM deliveries"))).scalar()
        assert events == 0
        assert deliveries == 0
